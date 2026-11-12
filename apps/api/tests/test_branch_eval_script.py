"""Unit tests for the F-02 auto-branch evaluation script; fake mode only, no network or provider."""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

from ramus_api.modules.conversations.domain.models import AuthorKind
from ramus_api.modules.conversations.domain.views import mentions_ai
from ramus_api.modules.execution.domain.models import ConversationContext
from ramus_api.modules.execution.domain.work import WORK_RULES

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
FAKE_KEY = "sk-test-not-a-real-key-123"


def _load_script():
    # Running a script file puts its directory on sys.path; reproduce that for the sibling eval_support import.
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import branch_eval_cases  # noqa: F401 - registers the sibling module like a direct script run does

    spec = importlib.util.spec_from_file_location("eval_auto_branch", SCRIPTS_DIR / "eval_auto_branch.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


script = _load_script()
cases = sys.modules["branch_eval_cases"]
support = sys.modules["eval_support"]


def _by_id(case_id: str, variant_id: str):
    return next(v for v in cases.VARIANTS if (v.case_id, v.variant_id) == (case_id, variant_id))


def _variants(case_id: str, gate: bool):
    return [v for v in cases.VARIANTS if v.case_id == case_id and v.gate == gate]


def _task(title: str, goal: str = "목표") -> object:
    return cases.TaskView(title, goal, "시작")


def _observation(mode: str | None, tasks=(), error: str | None = None):
    return cases.Observation(mode, "답변", tuple(tasks), None, error)


def _run(argv: list[str], factory=None, credentials=None) -> int:
    args = script.parse_args(argv)
    return asyncio.run(script.run_all(args, credentials=credentials, client_factory=factory))


def _records(tmp_path: Path, behavior: str, trials: int = 2, context: str = "none") -> list[dict]:
    argv = ["--mode", "fake", "--fake-behavior", behavior, "--trials", str(trials), "--context", context,
            "--out", str(tmp_path)]
    assert _run(argv) == 0
    (report,) = tmp_path.glob("branch_eval_fake_*.json")
    return json.loads(report.read_text(encoding="utf-8"))["records"]


# --------------------------------------------------------------------------- fixture integrity


def test_six_cases_with_expected_variant_counts():
    assert list(cases.CASE_LABELS) == [f"F02-{n}" for n in range(1, 7)]
    gate = [v for v in cases.VARIANTS if v.gate]
    model = [v for v in cases.VARIANTS if not v.gate]
    assert (len(gate), len(model)) == (3, 14)
    for case_id in ("F02-1", "F02-2", "F02-3"):
        assert (len(_variants(case_id, True)), len(_variants(case_id, False))) == (1, 2)
    assert [len(_variants(c, False)) for c in ("F02-4", "F02-5", "F02-6")] == [3, 2, 3]
    assert not any(_variants(c, True) for c in ("F02-4", "F02-5", "F02-6"))


def test_gate_bodies_skip_ai_and_model_requests_mention_it():
    for item in cases.VARIANTS:
        assert mentions_ai(item.messages[-1]) is (not item.gate)
        if item.gate:
            assert not any(mentions_ai(body) for body in item.messages)


def test_split_variants_list_scopes_and_others_do_not():
    for item in cases.VARIANTS:
        assert bool(item.scopes) == (item.expectation == "split")
    assert all(v.scopes == ("가입", "혜택", "해지") for v in _variants("F02-6", False))


def test_validate_variants_rejects_contradictions():
    bad_gate = cases.Variant("F02-1", "x", ("@AI 안녕",), "no_tasks", gate=True)
    bad_model = cases.Variant("F02-1", "x", ("안녕",), "no_tasks")
    for bad in (bad_gate, bad_model):
        with pytest.raises(ValueError):
            cases.validate_variants([bad])


# --------------------------------------------------------------------------- request through the handler


@pytest.mark.parametrize("variant", [v for v in cases.VARIANTS if not v.gate], ids=lambda v: f"{v.case_id}-{v.variant_id}")
def test_request_is_built_by_the_production_handler(variant):
    rig = script.build_rig(variant)
    request = rig.handler.build_request(None, rig.run, ConversationContext())
    assert request.messages[0].role == "system"
    assert request.messages[0].content == WORK_RULES
    assert request.is_child is False
    assert request.credential_account_id == rig.run.credential_account_id
    assert request.messages[-1].content == variant.messages[-1]
    earlier = request.messages[-len(variant.messages):-1]
    assert [m.content for m in earlier] == list(variant.messages[:-1])
    assert all(m.role == "user" for m in earlier)


# --------------------------------------------------------------------------- classification


SPLIT_VARIANT = _by_id("F02-6", "m1")
NO_TASKS_VARIANT = _by_id("F02-4", "m1")
EXECUTE_VARIANT = _by_id("F02-5", "m1")


def _three(*titles: str):
    return [_task(t) for t in titles]


@pytest.mark.parametrize(
    ("variant", "observation", "outcome"),
    [
        (NO_TASKS_VARIANT, _observation("answer"), "pass"),
        (NO_TASKS_VARIANT, _observation("clarify"), "pass"),
        (NO_TASKS_VARIANT, _observation("branch", _three("가입 조사")), "unnecessary_branch"),
        (SPLIT_VARIANT, _observation("answer"), "missing_branch"),
        (SPLIT_VARIANT, _observation("branch", _three("가입 조사", "혜택 조사")), "scope_mismatch"),
        (SPLIT_VARIANT, _observation("branch", _three("가입 조사", "혜택 조사", "해지 조사")), "pass"),
        (SPLIT_VARIANT, _observation("branch", _three("가입과 혜택 조사", "해지 조사", "기타")), "scope_mismatch"),
        (SPLIT_VARIANT, _observation("branch", _three("가입 조사", "혜택 조사", "탈퇴 조사")), "pass"),
        (SPLIT_VARIANT, _observation("branch", _three("가입 조사", "가입 사례", "혜택 조사")), "scope_mismatch"),
        (SPLIT_VARIANT, _observation("branch", _three("가입 조사", "혜택 조사", "해지 조사", "해지 보조")), "scope_mismatch"),
        (EXECUTE_VARIANT, _observation("answer"), "pass"),
        (EXECUTE_VARIANT, _observation("branch", _three("타사 조사 A", "타사 조사 B")), "pass"),
        (EXECUTE_VARIANT, _observation("clarify"), "held_for_clarify"),
        (EXECUTE_VARIANT, _observation(None, error="LLM_TIMEOUT"), "error"),
        (SPLIT_VARIANT, _observation(None, error="EXC_ValueError"), "error"),
    ],
)
def test_classification_table(variant, observation, outcome):
    assert cases.classify(variant, observation).outcome == outcome
    assert outcome in cases.OUTCOMES


def test_verdict_rejects_unknown_outcome():
    with pytest.raises(ValueError):
        cases.Verdict("maybe")


def test_split_records_matched_and_missing_scopes():
    verdict = cases.classify(SPLIT_VARIANT, _observation("branch", _three("가입 조사", "혜택 조사")))
    assert verdict.matched_scopes == ("가입", "혜택")
    assert verdict.missing_scopes == ("해지",)
    assert cases.classify(SPLIT_VARIANT, _observation("answer")).missing_scopes == ("가입", "혜택", "해지")


def test_title_without_scope_falls_back_to_goal():
    tasks = [_task("조사 1", "가입 사례 조사"), _task("조사 2", "혜택 사례 조사"), _task("조사 3", "해지 사례 조사")]
    assert cases.classify(SPLIT_VARIANT, _observation("branch", tasks)).outcome == "pass"


def test_title_scope_wins_over_goal_scope():
    tasks = [_task("가입 조사", "혜택도 함께"), _task("혜택 조사"), _task("해지 조사")]
    assert cases.classify(SPLIT_VARIANT, _observation("branch", tasks)).outcome == "pass"


def test_gate_result_requires_no_run():
    assert all(cases.evaluate_gate(v).no_run for v in cases.VARIANTS if v.gate)
    assert cases.evaluate_gate(NO_TASKS_VARIANT).no_run is False


# --------------------------------------------------------------------------- fake pipeline


def test_expected_behavior_passes_every_trial_and_gate_makes_no_calls(tmp_path):
    seen: list[httpx.Request] = []
    inner = script.make_fake_handler("expected")

    def counting(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return inner(request)

    factory = lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(counting), **kw)  # noqa: E731
    argv = ["--mode", "fake", "--trials", "2", "--out", str(tmp_path)]
    assert _run(argv, factory) == 0
    assert len(seen) == 14 * 2
    (report,) = tmp_path.glob("branch_eval_fake_*.json")
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert all(r["outcome"] == "pass" for r in payload["records"])
    assert payload["planned_calls"] == 28 and payload["fake_behavior"] == "expected"
    assert len(payload["gate"]) == 3 and all(g["no_run"] for g in payload["gate"])


def test_tasks_come_from_the_store_and_match_writer_children():
    variant = SPLIT_VARIANT
    gateway = script.build_gateway("fake-model", support.StaticCredentials(FAKE_KEY), script.fake_client_factory("expected"))
    rig_obs = {}

    async def go():
        rig = script.build_rig(variant)
        request = rig.handler.build_request(None, rig.run, ConversationContext())
        output = await gateway.complete(request)
        rig.handler.complete(None, rig.run, output)
        rig_obs["rig"], rig_obs["output"] = rig, output

    asyncio.run(go())
    rig = rig_obs["rig"]
    tasks = script.created_tasks(rig)
    assert len(tasks) == len(rig.tasks.created) == len(rig.writer.children) == 3
    assert [t.title for t in tasks] == [c.title for _, c in rig.writer.children]
    assert all(t.start_input for t in tasks)
    assert [m.body for _, m in rig.writer.messages if m.author_kind == AuthorKind.AI] == ["별도 작업 3개로 나눠 진행합니다."]
    observation = asyncio.run(script.observe(variant, gateway))
    assert observation.parent_message == "별도 작업 3개로 나눠 진행합니다."
    assert len(observation.tasks) == 3 and observation.error_code is None


def test_overbranch_makes_every_no_tasks_trial_unnecessary(tmp_path):
    records = _records(tmp_path, "overbranch")
    no_tasks = [r for r in records if r["expectation"] == "no_tasks"]
    assert no_tasks and all(r["outcome"] == "unnecessary_branch" and r["task_count"] == 2 for r in no_tasks)
    assert all(r["outcome"] == "pass" for r in records if r["expectation"] == "execute")
    assert all(r["outcome"] == "scope_mismatch" for r in records if r["expectation"] == "split")


def test_underbranch_makes_every_split_trial_missing(tmp_path):
    records = _records(tmp_path, "underbranch")
    assert all(r["outcome"] == "missing_branch" for r in records if r["expectation"] == "split")
    assert all(r["outcome"] == "pass" for r in records if r["expectation"] != "split")


def test_cases_filter_limits_variants_and_plan(tmp_path, capsys):
    argv = ["--mode", "fake", "--trials", "1", "--cases", "F02-5,F02-6", "--out", str(tmp_path)]
    assert _run(argv) == 0
    out = capsys.readouterr().out
    assert "plan: 5 model variants x 1 trials = 5 planned model calls" in out
    assert "gate (no @AI): 0/0 no run" in out
    assert "unnecessary branches: 0  missing branches: 0" in out


def test_summary_output_has_case_variant_gate_and_totals(tmp_path, capsys):
    assert _run(["--mode", "fake", "--fake-behavior", "overbranch", "--trials", "1", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "per case:" in out and "per variant:" in out and "사람 간 논의" in out
    assert "gate (no @AI): 3/3 no run" in out
    assert "unnecessary branches: 9  missing branches: 0" in out


# --------------------------------------------------------------------------- errors and safety


def test_provider_failure_is_recorded_as_error_code_without_message():
    def failing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "secret detail"}})

    factory = lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(failing), **kw)  # noqa: E731
    gateway = script.build_gateway("fake-model", support.StaticCredentials(FAKE_KEY), factory)
    observation = asyncio.run(script.observe(NO_TASKS_VARIANT, gateway))
    assert observation.error_code == "AI_CONNECTION_REQUIRED"
    assert cases.classify(NO_TASKS_VARIANT, observation).outcome == "error"


def test_unexpected_exception_maps_to_llm_unavailable_without_its_message():
    class Boom:
        async def complete(self, request):
            raise RuntimeError("secret detail")

    observation = asyncio.run(script.observe(NO_TASKS_VARIANT, Boom()))
    assert observation.error_code == "LLM_UNAVAILABLE"


def test_timeout_is_reported_as_llm_timeout():
    class Slow:
        async def complete(self, request):
            await asyncio.sleep(5)

    observation = asyncio.run(script.observe(NO_TASKS_VARIANT, Slow(), timeout=0.01))
    assert observation.error_code == "LLM_TIMEOUT"
    assert script.LLM_TIMEOUT_S == 120.0


def test_output_failure_from_the_handler_maps_to_its_code():
    class Bad:
        async def complete(self, request):
            return {"mode": "branch", "reply": "x", "tasks": []}

    observation = asyncio.run(script.observe(NO_TASKS_VARIANT, Bad()))
    assert observation.error_code == "LLM_OUTPUT_INVALID"


def test_max_calls_below_plan_exits_before_any_request(tmp_path, capsys):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(500)

    factory = lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler), **kw)  # noqa: E731
    argv = ["--mode", "fake", "--trials", "3", "--max-calls", "41", "--out", str(tmp_path)]
    with pytest.raises(SystemExit) as excinfo:
        _run(argv, factory)
    assert "exceed --max-calls" in str(excinfo.value)
    assert seen == [] and list(tmp_path.iterdir()) == []
    assert "42 planned model calls" in capsys.readouterr().out


def test_max_calls_is_checked_before_the_key_is_resolved(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    argv = ["--mode", "live", "--max-calls", "1", "--out", str(tmp_path)]
    with pytest.raises(SystemExit) as excinfo:
        _run(argv)
    assert "exceed --max-calls" in str(excinfo.value)


@pytest.mark.parametrize(
    "argv",
    [
        ["--mode", "live", "--fake-behavior", "overbranch"],
        ["--mode", "fake", "--trials", "0"],
        ["--mode", "fake", "--cases", "F02-9"],
        ["--mode", "fake", "--cases", "F02-1,nope"],
        ["--mode", "fake", "--concurrency", "0"],
        ["--mode", "fake", "--max-calls", "0"],
        ["--mode", "fake", "--fake-behavior", "other"],
    ],
)
def test_invalid_cli_arguments_exit_with_code_2(argv):
    with pytest.raises(SystemExit) as excinfo:
        script.parse_args(argv)
    assert excinfo.value.code == 2


def test_cli_defaults():
    args = script.parse_args(["--mode", "fake"])
    assert args.out == script.REPO_ROOT / "artifacts" / "branch-eval"
    assert (args.trials, args.concurrency, args.max_calls, args.fake_behavior) == (3, 4, 60, "expected")
    assert args.cases is None
    assert script.parse_args(["--mode", "live"]).fake_behavior is None
    assert (script.REPO_ROOT / "package.json").exists()


def test_report_and_stdout_never_contain_the_api_key(tmp_path, capsys):
    argv = ["--mode", "fake", "--trials", "1", "--out", str(tmp_path)]
    assert _run(argv, credentials=support.StaticCredentials(FAKE_KEY)) == 0
    out = capsys.readouterr()
    (report,) = tmp_path.glob("branch_eval_fake_*.json")
    assert FAKE_KEY not in report.read_text(encoding="utf-8")
    assert FAKE_KEY not in out.out + out.err


def test_report_has_required_fields(tmp_path):
    assert _run(["--mode", "fake", "--trials", "1", "--cases", "F02-6", "--out", str(tmp_path)]) == 0
    (report,) = tmp_path.glob("branch_eval_fake_*.json")
    payload = json.loads(report.read_text(encoding="utf-8"))
    for key in ("generated_at", "mode", "fake_behavior", "model", "trials", "concurrency", "planned_calls", "gate", "context", "complete"):
        assert key in payload
    record = payload["records"][0]
    for key in ("case_id", "variant_id", "trial", "messages", "expectation", "scopes", "mode", "reply", "tasks",
                "task_count", "parent_message", "context", "matched_scopes", "missing_scopes", "outcome", "error_code", "elapsed_s"):
        assert key in record
    assert set(record["tasks"][0]) == {"title", "goal", "start_input"}
    assert payload["complete"] is True and payload["context"] == "none"
    assert record["parent_message"] == "별도 작업 3개로 나눠 진행합니다." and record["context"] == "none"


# --------------------------------------------------------------------------- seeded context


def _context_payload(request) -> dict:
    assert request.messages[1].role == "user"
    return json.loads(request.messages[1].content.split("\n", 1)[1])


def test_service_brief_context_is_pinned_in_the_second_message():
    from ramus_api.modules.seed.domain.content import RESOURCES, sample_id

    brief = next(r for r in RESOURCES if r.key == "service-brief")
    context = cases.build_context("service-brief")
    rig = script.build_rig(NO_TASKS_VARIANT, context)
    request = rig.handler.build_request(None, rig.run, rig.context)
    assert request.context == context
    (resource,) = _context_payload(request)["resources"]
    assert resource["content"] == brief.body and resource["instructions"] is None
    assert resource["kind"] == "text" and resource["name"] == brief.name
    assert resource["revision_id"] == str(sample_id("resource:service-brief:v1"))
    assert resource["resource_id"] == str(sample_id("resource:service-brief"))
    assert cases.build_context("service-brief") == context


def test_none_context_has_no_resources():
    rig = script.build_rig(NO_TASKS_VARIANT)
    request = rig.handler.build_request(None, rig.run, rig.context)
    assert _context_payload(request)["resources"] == []
    assert cases.build_context("none") == ConversationContext()


def test_skill_resources_map_to_instructions():
    from ramus_api.modules.seed.domain.content import RESOURCES

    skill = next(r for r in RESOURCES if r.kind == "skill")
    item = cases.resource_input(skill)
    assert item.instructions == skill.body and item.content is None and item.kind == "skill"


def test_context_reaches_the_context_provider_for_branch_copies():
    context = cases.build_context("service-brief")
    rig = script.build_rig(SPLIT_VARIANT, context)
    gateway = script.build_gateway("fake-model", support.StaticCredentials(FAKE_KEY), script.fake_client_factory("expected"))
    observation = asyncio.run(_observe_rig(rig, gateway))
    assert len(observation) == 3
    for child_id, _ in rig.writer.children:
        assert rig.contexts.snapshot(None, child_id).resources == context.resources


async def _observe_rig(rig, gateway):
    request = rig.handler.build_request(None, rig.run, rig.context)
    rig.handler.complete(None, rig.run, await gateway.complete(request))
    return script.created_tasks(rig)


def test_unknown_context_exits_with_code_2():
    with pytest.raises(SystemExit) as excinfo:
        script.parse_args(["--mode", "fake", "--context", "nope"])
    assert excinfo.value.code == 2
    with pytest.raises(ValueError):
        cases.build_context("nope")


def test_fake_pipeline_with_service_brief_passes_and_records_context(tmp_path, capsys):
    records = _records(tmp_path, "expected", context="service-brief")
    assert all(r["outcome"] == "pass" and r["context"] == "service-brief" for r in records)
    (report,) = tmp_path.glob("branch_eval_fake_*.json")
    assert json.loads(report.read_text(encoding="utf-8"))["context"] == "service-brief"
    assert "context=service-brief" in capsys.readouterr().out


# --------------------------------------------------------------------------- interruption


def test_cancelled_run_writes_a_partial_report(tmp_path, capsys):
    inner = script.make_fake_handler("expected")
    stop_body = _by_id("F02-2", "m1").messages[-1]

    def interrupting(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if payload["input"][-1]["content"] == stop_body:
            raise asyncio.CancelledError
        return inner(request)

    factory = lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(interrupting), **kw)  # noqa: E731
    argv = ["--mode", "fake", "--trials", "1", "--concurrency", "1", "--out", str(tmp_path)]
    with pytest.raises(asyncio.CancelledError):
        _run(argv, factory)
    (report,) = tmp_path.glob("branch_eval_fake_*.json")
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["complete"] is False
    assert 0 < len(payload["records"]) < payload["planned_calls"]
    assert all(r["outcome"] == "pass" for r in payload["records"])
    assert "INCOMPLETE" in capsys.readouterr().out
