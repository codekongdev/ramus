import ast
import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from uuid import UUID

import pytest

from ramus_api.modules.execution.application.output_schema import output_json_schema, validate_output
from ramus_api.modules.execution.application.ports import ContextProvider, LlmGateway, RunRequester
from ramus_api.modules.execution.domain.models import (
    ConversationContext,
    LlmFailure,
    LlmMessage,
    LlmRequest,
    ResourceInput,
    ResultInput,
    RunInputSnapshot,
    RunPurpose,
    RunRequest,
    RunStatus,
    TaskStatus,
)
from ramus_api.modules.execution.fakes.context import FakeContextProvider
from ramus_api.modules.execution.fakes.llm import FakeLLM
from ramus_api.modules.execution.fakes.runs import FakeRunRequester
from ramus_api.shared.domain.errors import BusinessError

PROJECT, CONVERSATION, CHILD, ACCOUNT, OTHER_ACCOUNT, RESULT = (UUID(int=n) for n in range(1, 7))
WORK = LlmRequest(RunPurpose.WORK, (LlmMessage("user", "요청 내용"),), ACCOUNT)
SUMMARY = replace(WORK, purpose=RunPurpose.SUMMARY)
CHILD_WORK = replace(WORK, is_child=True)


def run_request(**changes) -> RunRequest:
    return replace(RunRequest(PROJECT, CONVERSATION, None, RunPurpose.WORK, None, ACCOUNT), **changes)


@pytest.mark.parametrize("llm_request", [WORK, CHILD_WORK, SUMMARY])
async def test_fake_llm_is_deterministic_and_injectable(llm_request) -> None:
    gateway: LlmGateway = FakeLLM()
    first, second = await gateway.complete(llm_request), await gateway.complete(llm_request)
    assert first == second
    with pytest.raises(TypeError):
        first["unexpected"] = True
    assert gateway.calls == (llm_request, llm_request)


async def test_explicit_branch_script_preserves_task_order_and_is_deeply_immutable() -> None:
    raw = json.dumps(
        {
            "mode": "branch",
            "reply": "두 작업을 진행합니다.",
            "tasks": [
                {"title": "경쟁사", "goal": "경쟁사 비교", "start_input": "비교 범위"},
                {"title": "예외", "goal": "예외 검토", "start_input": "반품 범위"},
            ],
        }
    )
    output = await FakeLLM(work_json=raw).complete(WORK)
    assert [task["title"] for task in output["tasks"]] == ["경쟁사", "예외"]
    with pytest.raises(TypeError):
        output["tasks"][0]["title"] = "변경"


@pytest.mark.parametrize(
    ("llm_request", "raw"),
    [
        (WORK, "not json"),
        (WORK, "[]"),
        (WORK, '{"mode":"answer","reply":"응답"}'),
        (WORK, '{"mode":"answer","reply":"응답","tasks":[],"api_key":"fixture-secret"}'),
        (WORK, '{"mode":"answer","reply":"응답","reply":"중복","tasks":[]}'),
        (WORK, '{"mode":"branch","reply":"응답","tasks":[]}'),
        (
            WORK,
            '{"mode":"answer","reply":"응답","tasks":[{"title":"작업","goal":"목표","start_input":"입력"}]}',
        ),
        (WORK, '{"mode":"answer","reply":123,"tasks":[]}'),
        (WORK, '{"mode":"answer","reply":"   ","tasks":[]}'),
        (WORK, '{"mode":"answer","reply":"응답","tasks":null}'),
        (WORK, '{"mode":"answer","reply":"응답","tasks":[],"bad":NaN}'),
        (CHILD_WORK, '{"mode":"branch","reply":"응답"}'),
        (CHILD_WORK, '{"mode":"answer","reply":"응답","tasks":[]}'),
        (SUMMARY, '{"conclusion":"결론","evidence":"추가 필드"}'),
        (SUMMARY, '{"conclusion":false}'),
        (SUMMARY, "{}"),
        (SUMMARY, '{"conclusion":""}'),
        (SUMMARY, '{"conclusion":"결론","conclusion":"중복"}'),
    ],
)
def test_model_boundary_rejects_bad_json_without_leaking_payload(llm_request, raw) -> None:
    with pytest.raises(LlmFailure) as caught:
        validate_output(llm_request, raw)
    assert caught.value.code == "LLM_OUTPUT_INVALID"
    assert caught.value.retryable
    assert "fixture-secret" not in str(caught.value)
    assert raw not in str(caught.value)


def test_model_boundary_rejects_too_many_or_incomplete_tasks_and_long_conclusion() -> None:
    task = {"title": "작업", "goal": "목표", "start_input": "입력"}
    for tasks in ([task] * 5, [{"title": "작업", "goal": "목표"}], [{**task, "extra": True}]):
        with pytest.raises(LlmFailure):
            validate_output(WORK, json.dumps({"mode": "branch", "reply": "시작", "tasks": tasks}))
    with pytest.raises(LlmFailure):
        validate_output(SUMMARY, json.dumps({"conclusion": "가" * 20_001}))


@pytest.mark.parametrize("llm_request", [WORK, CHILD_WORK, SUMMARY])
def test_schema_is_exportable_and_rejects_additional_properties(llm_request) -> None:
    schema = output_json_schema(llm_request)
    assert schema["additionalProperties"] is False
    assert json.loads(json.dumps(schema)) == schema
    if llm_request.purpose == RunPurpose.SUMMARY:
        assert schema["required"] == ["conclusion"]


async def test_fake_provider_failure_stays_a_failure() -> None:
    fake = FakeLLM(failure_code="LLM_TIMEOUT")
    with pytest.raises(LlmFailure, match="다시 시도") as caught:
        await fake.complete(WORK)
    assert caught.value.code == "LLM_TIMEOUT"
    assert fake.calls == (WORK,)


async def test_gateway_keeps_each_call_bound_to_its_explicit_credential_owner() -> None:
    fake = FakeLLM()
    await fake.complete(WORK)
    await fake.complete(replace(WORK, credential_account_id=OTHER_ACCOUNT))
    assert [call.credential_account_id for call in fake.calls] == [ACCOUNT, OTHER_ACCOUNT]
    assert "api_key" not in LlmRequest.__dataclass_fields__
    with pytest.raises(TypeError):
        LlmRequest(RunPurpose.WORK, ())


def test_context_pins_resource_and_result_versions_and_copies_only_resources() -> None:
    resource = ResourceInput(UUID(int=10), UUID(int=11), "skill", "스킬", "v1 지침", None)
    result = ResultInput(RESULT, UUID(int=12), 1, "결과", "v1 결론")
    resource_list, result_list = [resource], [result]
    context = ConversationContext(resource_list, result_list)
    fake: ContextProvider[object] = FakeContextProvider({CONVERSATION: context})
    snapshot = fake.snapshot(None, CONVERSATION)
    fake.copy_resources(None, CONVERSATION, CHILD)
    resource_list.clear()
    result_list.clear()
    fake.set_context(CONVERSATION, ConversationContext((replace(resource, revision_id=UUID(int=13)),), ()))
    assert snapshot == context
    assert snapshot.resources[0].instructions == "v1 지침"
    assert snapshot.results[0].conclusion == "v1 결론"
    assert fake.snapshot(None, CHILD) == ConversationContext((resource,), ())
    with pytest.raises(FrozenInstanceError):
        snapshot.resources[0].name = "변경"


def test_copy_resources_preserves_target_results_and_empty_context_is_explicit() -> None:
    result = ResultInput(RESULT, UUID(int=12), 1, "결과", "결론")
    fake = FakeContextProvider({CHILD: ConversationContext(results=(result,))})
    fake.copy_resources(None, CONVERSATION, CHILD)
    assert fake.snapshot(None, CHILD).results == (result,)
    assert fake.snapshot(None, CONVERSATION) == ConversationContext()
    with pytest.raises(ValueError):
        ConversationContext(results=(result, result))


def test_registration_uses_requesters_connection_and_active_target_rules() -> None:
    fake: RunRequester[object] = FakeRunRequester([ACCOUNT])
    with pytest.raises(BusinessError) as missing:
        fake.request(None, run_request(requested_by=OTHER_ACCOUNT))
    assert (missing.value.code, missing.value.status) == ("AI_CONNECTION_REQUIRED", 409)
    assert fake.requests == ()
    work = fake.request(None, run_request())
    assert work.status == RunStatus.PENDING
    with pytest.raises(BusinessError) as active:
        fake.request(None, run_request())
    assert (active.value.code, active.value.status) == ("ACTIVE_RUN_EXISTS", 409)
    # Different child and a summary target remain independently registrable.
    child = fake.request(None, run_request(conversation_id=CHILD))
    summary_request = run_request(purpose=RunPurpose.SUMMARY, target_id=RESULT)
    summary = fake.request(None, summary_request)
    with pytest.raises(BusinessError):
        fake.request(None, replace(summary_request, conversation_id=CHILD))
    fake.set_status(work.run_id, RunStatus.SUCCEEDED)
    retry = fake.request(None, run_request())
    assert len({work.run_id, child.run_id, summary.run_id, retry.run_id}) == 4
    fake.set_connected(ACCOUNT, False)
    with pytest.raises(BusinessError):
        fake.request(None, run_request(conversation_id=UUID(int=50)))


def test_fake_run_ids_are_reproducible_and_requests_do_not_contain_keys() -> None:
    first = FakeRunRequester([ACCOUNT]).request(None, run_request())
    second = FakeRunRequester([ACCOUNT]).request(None, run_request())
    assert first == second
    assert set(RunRequest.__dataclass_fields__) == {
        "project_id",
        "conversation_id",
        "task_id",
        "purpose",
        "target_id",
        "requested_by",
    }


def test_purpose_and_message_ranges_are_explicit() -> None:
    with pytest.raises(ValueError):
        run_request(purpose=RunPurpose.SUMMARY)
    with pytest.raises(ValueError):
        run_request(target_id=RESULT)
    for start, end in ((1, None), (None, 1), (0, 1), (3, 2)):
        with pytest.raises(ValueError):
            RunInputSnapshot(start, end)
    assert RunInputSnapshot(1, 2).message_to_seq == 2
    assert {item.value for item in RunStatus} == {"pending", "running", "succeeded", "failed", "cancelled"}
    assert {item.value for item in TaskStatus} == {"pending", "running", "ready", "failed", "cancelled"}


def test_domain_and_ports_do_not_import_frameworks_orms_or_sdks() -> None:
    root = Path(__file__).resolve().parents[1] / "src/ramus_api/modules"
    for path in (*root.glob("*/domain/*.py"), *root.glob("*/application/ports.py")):
        imports = []
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        assert not any(
            name.split(".")[0] in {"fastapi", "pydantic", "sqlalchemy", "openai"} for name in imports
        ), path
