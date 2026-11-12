"""Evaluation harness: how does the real model decide F-02 auto-branching (answer / clarify / branch)?

Runs the six F-02 cases plus variant sentences through the production work path (WorkPurposeHandler
-> LongSummaryGateway -> OpenAiGateway) with in-memory adapters; no database and no worker are involved.
Each trial is classified, and unnecessary branches (tasks created when none were wanted) and missing
branches (no tasks when an explicit split was requested) are counted separately.

Run from the repository root:
  pnpm api:eval-branch --mode fake                      # in-process httpx MockTransport, no provider
  uv run --project apps/api python apps/api/scripts/eval_auto_branch.py --mode live --env-file <path>
                                                        # real provider, costs money
  Add --context service-brief to pin the seeded "가상 서비스 기본 정보" resource, as in the sample project.
  Do not pass --env-file through pnpm: pnpm consumes it and loads the whole file into the environment.

Cost and safety notes:
- Live mode calls the real provider: by default 14 model variants x 3 trials = 42 calls (cap: --max-calls).
  It is not part of ``pnpm verify``.
- The plan is printed first; if it exceeds --max-calls the script exits before the key is read or any call.
- Gate variants (messages without @AI) never create a run in production, so they make no model call.
- Live mode reads only OPENAI_API_KEY (from --env-file, else the environment). The key is never printed,
  logged or written, and raw provider payloads are never printed.
- Reports contain synthetic data only and are written to ``artifacts/branch-eval/`` (gitignored).
"""

import argparse
import asyncio
import json
import os
import secrets
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
from branch_eval_cases import (
    CASE_LABELS,
    CONTEXTS,
    SPLIT,
    VARIANTS,
    GateResult,
    Observation,
    Stats,
    TaskView,
    TrialRecord,
    Variant,
    aggregate,
    build_context,
    evaluate_gate,
    make_record,
    select_variants,
)
from eval_support import StaticCredentials, resolve_api_key

from ramus_api.modules.conversations.domain.models import AuthorKind
from ramus_api.modules.conversations.fakes.writer import FakeConversationWriter
from ramus_api.modules.execution.application.branch_ports import NewBranchTask
from ramus_api.modules.execution.application.config import ExecutorConfig
from ramus_api.modules.execution.application.work import WorkPurposeHandler
from ramus_api.modules.execution.domain.models import (
    ConversationContext,
    RunInputSnapshot,
    RunPurpose,
    RunStatus,
    RunView,
)
from ramus_api.modules.execution.domain.state import failure_from_exception
from ramus_api.modules.execution.domain.work import WorkHistory, WorkMessage
from ramus_api.modules.execution.fakes.context import FakeContextProvider
from ramus_api.modules.execution.fakes.runs import FakeRunRequester
from ramus_api.modules.execution.infrastructure.summary_gateway import OpenAiGateway
from ramus_api.modules.results.application.long_summary import LongSummaryGateway

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = REPO_ROOT / "artifacts" / "branch-eval"
DEFAULT_TRIALS, DEFAULT_CONCURRENCY, DEFAULT_MAX_CALLS = 3, 4, 60
FAKE_BEHAVIORS = ("expected", "overbranch", "underbranch")
LLM_TIMEOUT_S = ExecutorConfig().llm_timeout.total_seconds()  # same per-call timeout as the worker

# --------------------------------------------------------------------------- production path (shell)


class InMemoryWorkInputs:
    """WorkInputReader returning one fixed history; there is no database."""

    def __init__(self, history: WorkHistory) -> None:
        self._history = history

    def read(self, session: object, conversation_id: UUID, run_id: UUID) -> WorkHistory:
        return self._history

    def lock_parent(self, session: object, conversation_id: UUID) -> None:
        return None


class RecordingBranchTasks:
    """BranchTaskStore that records created tasks in memory."""

    def __init__(self) -> None:
        self.created: list[NewBranchTask] = []

    def create(self, session: object, task: NewBranchTask) -> None:
        self.created.append(task)

    def goal(self, session: object, task_id: UUID) -> str:
        return next(task.goal for task in self.created if task.id == task_id)


@dataclass(frozen=True)
class TrialRig:
    run: RunView
    handler: WorkPurposeHandler
    writer: FakeConversationWriter
    tasks: RecordingBranchTasks
    context: ConversationContext
    contexts: FakeContextProvider


def build_rig(variant: Variant, context: ConversationContext | None = None) -> TrialRig:
    """One run over the variant's conversation; only the last message carries the run id."""
    context = context or ConversationContext()
    account, run_id, project_id = uuid4(), uuid4(), uuid4()
    last = len(variant.messages)
    messages = tuple(
        WorkMessage(seq, AuthorKind.HUMAN, body, run_id if seq == last else None)
        for seq, body in enumerate(variant.messages, start=1)
    )
    conversation_id = uuid4()
    run = RunView(run_id, project_id, conversation_id, None, RunPurpose.WORK, None, RunStatus.RUNNING, account,
                  account, RunInputSnapshot())
    writer, tasks = FakeConversationWriter(), RecordingBranchTasks()
    contexts = FakeContextProvider({conversation_id: context})
    handler = WorkPurposeHandler(
        inputs=InMemoryWorkInputs(WorkHistory(project_id, None, False, messages)), writer=writer, tasks=tasks,
        contexts=contexts, requester=FakeRunRequester(connected_accounts=[account]),
    )
    return TrialRig(run, handler, writer, tasks, context, contexts)


def created_tasks(rig: TrialRig) -> tuple[TaskView, ...]:
    """Tasks as stored (title, goal) joined with each child's start input from the writer's SYSTEM message."""
    starts = {m.conversation_id: m.body for _, m in rig.writer.messages if m.author_kind == AuthorKind.SYSTEM}
    return tuple(TaskView(t.title, t.goal, starts.get(t.child_conversation_id, "")) for t in rig.tasks.created)


def _parent_message(rig: TrialRig) -> str | None:
    bodies = [m.body for _, m in rig.writer.messages
              if m.author_kind == AuthorKind.AI and m.conversation_id == rig.run.conversation_id]
    return bodies[-1] if bodies else None


async def observe(variant: Variant, gateway: Any, context: ConversationContext | None = None,
                  timeout: float = LLM_TIMEOUT_S) -> Observation:
    """Runs one trial through the handler; failures are reduced to the worker's stored error code."""
    rig = build_rig(variant, context)
    mode, reply = None, ""
    try:
        request = rig.handler.build_request(None, rig.run, rig.context)
        output = await asyncio.wait_for(gateway.complete(request), timeout)
        mode, reply = str(output["mode"]), str(output["reply"])
        rig.handler.complete(None, rig.run, output)
    except Exception as error:  # noqa: BLE001 - mapped to a code like the worker; messages are never printed
        return Observation(mode, reply, created_tasks(rig), _parent_message(rig), failure_from_exception(error).code)
    return Observation(mode, reply, created_tasks(rig), _parent_message(rig))


def build_gateway(model: str, credentials: Any, client_factory: Callable[..., httpx.AsyncClient] | None) -> Any:
    # LongSummaryGateway is kept to mirror create_app; it passes WORK requests through unchanged.
    kwargs = {"client_factory": client_factory} if client_factory else {}
    return LongSummaryGateway(OpenAiGateway(model, credentials, **kwargs))


# --------------------------------------------------------------------------- fake provider


def _task_json(title: str, goal: str, start_input: str) -> dict[str, str]:
    return {"title": title, "goal": goal, "start_input": start_input}


def fake_output(behavior: str, variant: Variant | None) -> dict[str, Any]:
    """Model output for the fake provider; satisfies the strict ParentWorkOutput schema."""
    answer: dict[str, Any] = {"mode": "answer", "reply": "요청하신 내용을 정리해 답변드립니다.", "tasks": []}
    if behavior == "underbranch" or variant is None:
        return answer
    if behavior == "overbranch":
        tasks = [_task_json(f"작업 {n}", f"{n}번 조사를 수행한다", f"{n}번 조사를 시작해 주세요.") for n in (1, 2)]
        return {"mode": "branch", "reply": "작업을 나눠 진행합니다.", "tasks": tasks}
    if variant.expectation != SPLIT:
        return answer
    tasks = [_task_json(f"{s} 벤치마킹", f"경쟁사 멤버십의 {s} 사례를 벤치마킹한다", f"{s} 범위로 벤치마킹을 진행해 주세요.")
             for s in variant.scopes]
    return {"mode": "branch", "reply": "범위별로 나눠 진행합니다.", "tasks": tasks}


def make_fake_handler(behavior: str, variants: Sequence[Variant] = VARIANTS) -> Callable[[httpx.Request], httpx.Response]:
    by_last = {v.messages[-1]: v for v in variants if not v.gate}

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        last_user = next(item["content"] for item in reversed(payload["input"]) if item["role"] == "user")
        text = json.dumps(fake_output(behavior, by_last.get(last_user)), ensure_ascii=False)
        return httpx.Response(200, json={"status": "completed", "error": None, "output": [{
            "type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": text}]}]})
    return handler


def fake_client_factory(behavior: str) -> Callable[..., httpx.AsyncClient]:
    handler = make_fake_handler(behavior)
    return lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)


# --------------------------------------------------------------------------- reporting


def trial_line(record: TrialRecord) -> str:
    titles = " | ".join(task.title for task in record.tasks) or "-"
    error = f" error={record.error_code}" if record.error_code else ""
    return (f"[{record.case_id}/{record.variant_id} #{record.trial}] mode={record.mode or '-'} "
            f"tasks={record.task_count} [{titles}] -> {record.outcome}{error}")


def _stats_row(name: str, stats: Stats, label: str = "") -> str:
    count = stats.outcomes.get
    pct = f"{100 * stats.passes / stats.attempts:.0f}%" if stats.attempts else "-"
    modes = " ".join(f"{k}:{v}" for k, v in sorted(stats.modes.items())) or "-"
    return (f"{name:<9} {stats.attempts:>3} {stats.passes:>5} {pct:>5} {count('unnecessary_branch', 0):>6} "
            f"{count('missing_branch', 0):>7} {count('scope_mismatch', 0):>5} {count('held_for_clarify', 0):>5} "
            f"{count('error', 0):>3}  {modes}  {label}").rstrip()


TABLE_HEADER = f"{'':<9} {'n':>3} {'pass':>5} {'pass%':>5} {'unnec':>6} {'missing':>7} {'scope':>5} {'held':>5} {'err':>3}  modes"


def summary_lines(records: Sequence[TrialRecord], gates: Sequence[GateResult]) -> list[str]:
    lines = ["per case:", TABLE_HEADER]
    for case_id in CASE_LABELS:
        rows = [r for r in records if r.case_id == case_id]
        if rows:
            lines.append(_stats_row(case_id, aggregate(rows), CASE_LABELS[case_id]))
    lines += ["per variant:", TABLE_HEADER]
    for key in sorted({(r.case_id, r.variant_id) for r in records}):
        rows = [r for r in records if (r.case_id, r.variant_id) == key]
        lines.append(_stats_row("/".join(key), aggregate(rows)))
    lines.append(f"gate (no @AI): {sum(g.no_run for g in gates)}/{len(gates)} no run")
    codes = sorted({r.error_code for r in records if r.error_code})
    lines.append(f"unnecessary branches: {sum(r.outcome == 'unnecessary_branch' for r in records)}  "
                 f"missing branches: {sum(r.outcome == 'missing_branch' for r in records)}"
                 + (f"  error codes: {', '.join(codes)}" if codes else ""))
    return lines


def report_payload(args: argparse.Namespace, planned: int, gates: Sequence[GateResult],
                   records: Sequence[TrialRecord], complete: bool) -> dict[str, Any]:
    ordered = sorted(records, key=lambda r: (r.case_id, r.variant_id, r.trial))
    return {"generated_at": datetime.now().isoformat(timespec="seconds"), "mode": args.mode,
            "complete": complete, "fake_behavior": args.fake_behavior, "context": args.context,
            "model": args.model, "trials": args.trials, "concurrency": args.concurrency,
            "planned_calls": planned, "gate": [asdict(g) for g in gates], "records": [asdict(r) for r in ordered]}


def write_report(out_dir: Path, mode: str, payload: Mapping[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"
    path = out_dir / f"branch_eval_{mode}_{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- orchestration


async def run_trial(variant: Variant, trial: int, gateway: Any, semaphore: asyncio.Semaphore,
                    context_name: str, sink: list[TrialRecord]) -> None:
    """Runs one trial and appends its record to ``sink`` at once, so an interrupted run keeps paid results."""
    async with semaphore:
        started = time.perf_counter()
        observation = await observe(variant, gateway, build_context(context_name))
        record = make_record(variant, trial, context_name, observation, time.perf_counter() - started)
    sink.append(record)
    print(trial_line(record), flush=True)


def print_plan(model_variants: Sequence[Variant], gate_variants: Sequence[Variant], args: argparse.Namespace) -> int:
    planned = len(model_variants) * args.trials
    print(f"plan: {len(model_variants)} model variants x {args.trials} trials = {planned} planned model calls "
          f"(max {args.max_calls}); context={args.context}; {len(gate_variants)} gate variants make no model call",
          flush=True)
    return planned


async def _run_trials(args: argparse.Namespace, variants: Sequence[Variant], gateway: Any,
                      sink: list[TrialRecord]) -> bool:
    """Returns True when every trial finished; cancels leftovers and re-raises on interruption."""
    semaphore = asyncio.Semaphore(args.concurrency)
    tasks = [asyncio.ensure_future(run_trial(v, n, gateway, semaphore, args.context, sink))
             for v in variants for n in range(1, args.trials + 1)]
    try:
        await asyncio.gather(*tasks)
        return True
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def run_all(args: argparse.Namespace, *, credentials: Any = None,
                  client_factory: Callable[..., httpx.AsyncClient] | None = None) -> int:
    gate_variants, model_variants = select_variants(args.cases)
    planned = print_plan(model_variants, gate_variants, args)
    if planned > args.max_calls:
        sys.exit(f"Planned calls ({planned}) exceed --max-calls ({args.max_calls}); nothing was called.")
    live = args.mode == "live"
    if credentials is None:
        credentials = StaticCredentials(resolve_api_key(args.env_file) if live else "dummy-not-a-real-key")
    if client_factory is None and not live:
        client_factory = fake_client_factory(args.fake_behavior)
    gateway = build_gateway(args.model, credentials, client_factory)
    gates = [evaluate_gate(v) for v in gate_variants]
    for g in gates:
        print(f"[{g.case_id}/{g.variant_id}] gate: no @AI -> {'no run' if g.no_run else 'RUN CREATED'}", flush=True)
    records: list[TrialRecord] = []
    complete = False
    try:
        complete = await _run_trials(args, model_variants, gateway, records)
    finally:  # also on cancellation or Ctrl-C: keep what was already paid for
        path = write_report(args.out, args.mode, report_payload(args, planned, gates, records, complete))
        print()
        print("\n".join(summary_lines(records, gates)))
        print(f"report: {path}" + ("" if complete else "  (INCOMPLETE: run was interrupted)"))
    return 0


# --------------------------------------------------------------------------- CLI


def _case_list(value: str) -> tuple[str, ...]:
    ids = tuple(part.strip() for part in value.split(",") if part.strip())
    unknown = [i for i in ids if i not in CASE_LABELS]
    if not ids or unknown:
        raise argparse.ArgumentTypeError(f"unknown case id(s) {unknown or value!r}; choose from {', '.join(CASE_LABELS)}")
    return ids


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate F-02 auto-branching decisions of the Ramus work path.")
    parser.add_argument("--mode", choices=("fake", "live"), required=True)
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--cases", type=_case_list, help="comma-separated case ids, e.g. F02-4,F02-6 (default: all)")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-6-luna"))
    parser.add_argument("--env-file", help="dotenv-style file; only OPENAI_API_KEY is read")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="report directory (default: %(default)s)")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--max-calls", type=int, default=DEFAULT_MAX_CALLS, help="refuse to run above this many model calls")
    parser.add_argument("--context", choices=CONTEXTS, default="none",
                        help="applied resources: none = new conversation, service-brief = seeded sample brief")
    parser.add_argument("--fake-behavior", choices=FAKE_BEHAVIORS, help="fake mode only (default: expected)")
    args = parser.parse_args(argv)
    if args.fake_behavior and args.mode != "fake":
        parser.error("--fake-behavior is only valid with --mode fake")
    if args.mode == "fake" and args.fake_behavior is None:
        args.fake_behavior = "expected"
    for name in ("trials", "concurrency", "max_calls"):
        if getattr(args, name) < 1:
            parser.error(f"--{name.replace('_', '-')} must be >= 1")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(run_all(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
