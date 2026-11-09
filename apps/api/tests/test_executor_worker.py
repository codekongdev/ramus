"""Worker claim/execute/finish, cancellation, recovery, and input pinning on PostgreSQL."""

import asyncio
import logging
import threading
from datetime import timedelta
from uuid import UUID

import pytest
from executor_harness import (
    FAST,
    GatedLLM,
    ManualClock,
    Rig,
    ScriptedLLM,
    Seed,
    build_rig,
    drain,
    eventually,
    register,
    run_row,
    seed_rows,
    set_run,
    statuses,
    summary_request,
    work_request,
)
from sqlalchemy import select, update

from ramus_api.modules.execution.application.config import ExecutorConfig
from ramus_api.modules.execution.domain.models import (
    ConversationContext,
    ResourceInput,
    ResultInput,
    RunPurpose,
    RunStatus,
)
from ramus_api.modules.execution.fakes.handlers import FakeRunPurposeHandler
from ramus_api.modules.execution.fakes.llm import FakeLLM
from ramus_api.modules.execution.infrastructure.run_store import SqlRunStore
from ramus_api.modules.realtime.domain.events import ProjectEvent
from ramus_api.modules.realtime.fakes.publisher import FakeEventPublisher
from ramus_api.orm_registry import metadata
from ramus_api.shared.infrastructure.database import Database

pytestmark = pytest.mark.integration


@pytest.fixture
def seed(database: Database) -> Seed:
    # Workers claim every pending run in the database. The session database is shared by all tests,
    # so runs other tests left active are closed first to keep each test's queue its own.
    with database.transaction() as session:
        run = metadata.tables["run"]
        session.execute(
            update(run).where(run.c.status.in_(["pending", "running"])).values(status="cancelled")
        )
    return seed_rows(database, conversations=6)


class CommittedStatePublisher(FakeEventPublisher):
    """Records the run status other connections can see at the moment each event is published."""

    def __init__(self, database: Database) -> None:
        super().__init__()
        self._database = database
        self.visible: list[tuple[str, str]] = []

    async def publish(self, event: ProjectEvent) -> None:
        with self._database.engine.connect() as connection:
            table = metadata.tables["run"]
            status = connection.execute(
                select(table.c.status).where(table.c.id == event.data["run"]["id"])
            ).scalar_one()
        self.visible.append((event.data["run"]["status"], status))
        await super().publish(event)


# --- 3. normal flow --------------------------------------------------------------------------------


async def test_pending_run_succeeds_and_events_follow_each_commit(database: Database, seed: Seed) -> None:
    publisher = CommittedStatePublisher(database)
    rig = build_rig(database, seed, publisher=publisher)
    run_id = register(database, rig, work_request(seed, seed.conversations[0]))
    await rig.runtime.relay.flush()
    assert await rig.runtime.worker.run_once() is True
    assert await rig.runtime.worker.run_once() is False
    row = run_row(database, run_id)
    assert row["status"] == "succeeded" and row["finished_at"] is not None and row["started_at"] is not None
    assert [(run.id, dict(output)["mode"]) for run, output in rig.handler.completed] == [(run_id, "answer")]
    assert rig.handler.failed == ()
    await rig.runtime.relay.flush()
    assert statuses(publisher.events, run_id) == ["pending", "running", "succeeded"]
    assert publisher.visible == [("pending", "pending"), ("running", "running"), ("succeeded", "succeeded")]


# --- 2. concurrent workers -------------------------------------------------------------------------


async def test_two_workers_claim_each_run_once_and_call_the_model_once(
    database: Database, seed: Seed
) -> None:
    model = FakeLLM()
    first = build_rig(database, seed, gateway=model)
    second = build_rig(database, seed, gateway=model)
    run_ids = {register(database, first, work_request(seed, c)) for c in seed.conversations}
    counts = await asyncio.gather(drain(first), drain(second))
    assert sum(counts) == len(run_ids)
    assert len(model.calls) == len(run_ids)
    completed = [run.id for run, _ in (*first.handler.completed, *second.handler.completed)]
    assert sorted(completed) == sorted(run_ids)
    assert {run_row(database, run_id)["status"] for run_id in run_ids} == {"succeeded"}


def test_simultaneous_claims_of_one_pending_run_hand_it_to_one_session(
    database: Database, seed: Seed
) -> None:
    rig = build_rig(database, seed)
    run_id = register(database, rig, work_request(seed, seed.conversations[0]))
    store, barrier, claimed = SqlRunStore(), threading.Barrier(4), []

    def claim() -> None:
        with database.transaction() as session:
            barrier.wait(5)
            claimed.append(store.claim_next(session, frozenset({"work"}), rig.clock()))

    threads = [threading.Thread(target=claim) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert [state.id for state in claimed if state is not None] == [run_id]


# --- 4. invalid output and retry -------------------------------------------------------------------


async def test_invalid_output_fails_retryably_and_a_retry_runs_attempt_two(
    database: Database, seed: Seed
) -> None:
    model = ScriptedLLM(FakeLLM(work_json="not json"), FakeLLM())
    rig = build_rig(database, seed, gateway=model)
    run_id = register(database, rig, work_request(seed, seed.conversations[0]))
    await rig.runtime.worker.run_once()
    row = run_row(database, run_id)
    assert (row["status"], row["error_code"], row["error_params"]) == ("failed", "LLM_OUTPUT_INVALID", None)
    ((failed_run, error),) = rig.handler.failed
    assert (failed_run.id, error.code, error.retryable) == (run_id, "LLM_OUTPUT_INVALID", True)
    assert error.message == "AI 응답 형식이 올바르지 않습니다. 다시 시도해 주세요."

    with database.transaction() as session:
        rig.runtime.control.retry(session, run_id, seed.owner)
    await rig.runtime.worker.run_once()
    row = run_row(database, run_id)
    assert (row["status"], row["attempt"], row["error_code"]) == ("succeeded", 2, None)
    assert [run.id for run, _ in rig.handler.completed] == [run_id]
    assert len(model.calls) == 2
    await rig.runtime.relay.flush()
    assert statuses(rig.publisher.events, run_id) == [
        "pending",
        "running",
        "failed",
        "pending",
        "running",
        "succeeded",
    ]


def rename_then_fail(session, run, *_args) -> None:
    conversation = metadata.tables["conversation"]
    session.execute(
        update(conversation).where(conversation.c.id == run.conversation_id).values(title="바뀐 제목")
    )
    raise RuntimeError("handler secret")


def raise_secret(*_args) -> None:
    raise RuntimeError("handler secret")


async def test_complete_failure_rolls_back_its_writes_and_fails_retryably(
    database: Database, seed: Seed
) -> None:
    handler = FakeRunPurposeHandler(complete_hook=rename_then_fail)
    rig = build_rig(database, seed, handlers=[handler])
    run_id = register(database, rig, work_request(seed, seed.conversations[0]))
    await rig.runtime.worker.run_once()
    row = run_row(database, run_id)
    assert (row["status"], row["error_code"]) == ("failed", "LLM_UNAVAILABLE")
    assert handler.completed == ()
    assert [(run.id, error.code) for run, error in handler.failed] == [(run_id, "LLM_UNAVAILABLE")]
    with database.transaction() as session:
        conversation = metadata.tables["conversation"]
        title = session.execute(
            select(conversation.c.title).where(conversation.c.id == seed.conversations[0])
        ).scalar_one()
    assert title == "대화"  # the handler's write inside complete() was rolled back


async def test_build_request_or_fail_handler_errors_still_finish_the_run(
    database: Database, seed: Seed, caplog
) -> None:
    handler = FakeRunPurposeHandler(build_hook=raise_secret, fail_hook=raise_secret)
    rig = build_rig(database, seed, handlers=[handler])
    run_id = register(database, rig, work_request(seed, seed.conversations[0]))
    await rig.runtime.worker.run_once()
    assert (run_row(database, run_id)["status"], run_row(database, run_id)["error_code"]) == (
        "failed",
        "LLM_UNAVAILABLE",
    )
    assert "RuntimeError" in caplog.text and "handler secret" not in caplog.text


async def test_model_timeout_fails_with_a_timeout_code(database: Database, seed: Seed) -> None:
    config = ExecutorConfig(
        heartbeat_interval=timedelta(seconds=1),
        stale_after=timedelta(seconds=5),
        llm_timeout=timedelta(milliseconds=50),
    )
    rig = build_rig(database, seed, gateway=GatedLLM(), config=config)
    run_id = register(database, rig, work_request(seed, seed.conversations[0]))
    await rig.runtime.worker.run_once()
    assert run_row(database, run_id)["error_code"] == "LLM_TIMEOUT"


# --- 5. cancellation during the model call ---------------------------------------------------------


async def test_cancel_in_the_same_process_aborts_the_call(database: Database, seed: Seed) -> None:
    model = GatedLLM()
    rig = build_rig(database, seed, gateway=model)
    run_id = register(database, rig, work_request(seed, seed.conversations[0]))
    worker = asyncio.create_task(rig.runtime.worker.run_once())
    await asyncio.wait_for(model.started.wait(), 5)

    def cancel() -> None:
        with database.transaction() as session:
            rig.runtime.control.cancel(session, run_id, seed.owner)

    await asyncio.to_thread(cancel)
    assert await asyncio.wait_for(worker, 5) is True  # returns without the gate ever opening
    assert run_row(database, run_id)["status"] == "cancelled"
    assert (rig.handler.completed, rig.handler.failed) == ((), ())
    await rig.runtime.relay.flush()
    assert statuses(rig.publisher.events, run_id) == ["pending", "running", "cancelled"]


async def test_late_result_after_a_cancel_elsewhere_is_discarded(
    database: Database, seed: Seed, caplog
) -> None:
    caplog.set_level(logging.INFO)
    model = GatedLLM()
    config = ExecutorConfig(heartbeat_interval=timedelta(seconds=30), stale_after=timedelta(seconds=60))
    rig = build_rig(database, seed, gateway=model, config=config)
    elsewhere = build_rig(database, seed)  # another process: it cannot reach this worker's call
    run_id = register(database, rig, work_request(seed, seed.conversations[0]))
    worker = asyncio.create_task(rig.runtime.worker.run_once())
    await asyncio.wait_for(model.started.wait(), 5)
    with database.transaction() as session:
        elsewhere.runtime.control.cancel(session, run_id, seed.owner)
    model.release.set()
    await asyncio.wait_for(worker, 5)
    assert run_row(database, run_id)["status"] == "cancelled"
    assert rig.handler.completed == ()
    assert "discarded" in caplog.text


async def test_heartbeat_notices_a_cancel_elsewhere_and_stops_the_call(
    database: Database, seed: Seed
) -> None:
    model = GatedLLM()
    rig = build_rig(database, seed, gateway=model)  # FAST: 50 ms heartbeat
    elsewhere = build_rig(database, seed)
    run_id = register(database, rig, work_request(seed, seed.conversations[0]))
    worker = asyncio.create_task(rig.runtime.worker.run_once())
    await asyncio.wait_for(model.started.wait(), 5)
    with database.transaction() as session:
        elsewhere.runtime.control.cancel(session, run_id, seed.owner)
    assert await asyncio.wait_for(worker, 5) is True
    assert not model.release.is_set()
    assert rig.handler.completed == ()


async def test_heartbeat_refreshes_while_the_model_runs(database: Database, seed: Seed) -> None:
    model = GatedLLM()
    rig = build_rig(database, seed, gateway=model)
    run_id = register(database, rig, work_request(seed, seed.conversations[0]))
    worker = asyncio.create_task(rig.runtime.worker.run_once())
    await asyncio.wait_for(model.started.wait(), 5)
    claimed_at = run_row(database, run_id)["heartbeat_at"]
    rig.clock.advance(timedelta(seconds=7))
    await eventually(lambda: run_row(database, run_id)["heartbeat_at"] == rig.clock())
    assert run_row(database, run_id)["started_at"] == claimed_at
    model.release.set()
    await asyncio.wait_for(worker, 5)
    assert run_row(database, run_id)["status"] == "succeeded"


# --- 6. recovery and restart -----------------------------------------------------------------------


async def crash_while_running(rig: Rig, model: GatedLLM) -> None:
    """Simulates a dying process: the worker task is killed mid-call and never finishes the run."""
    task = asyncio.create_task(rig.runtime.worker.run_once())
    await asyncio.wait_for(model.started.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_restart_recovers_stale_and_expired_runs_and_claims_remaining_pending(
    database: Database, seed: Seed
) -> None:
    model = GatedLLM()
    old = build_rig(database, seed, gateway=model)
    stale = register(database, old, work_request(seed, seed.conversations[0]))
    await crash_while_running(old, model)
    assert run_row(database, stale)["status"] == "running"
    expired = register(database, old, work_request(seed, seed.conversations[1]))
    set_run(database, expired, created_at=old.clock() - timedelta(hours=1))
    remaining = register(database, old, work_request(seed, seed.conversations[2]))

    clock = ManualClock()
    clock.now = old.clock() + FAST.stale_after + timedelta(seconds=1)
    fresh = build_rig(database, seed, clock=clock)
    assert await fresh.runtime.worker.recover() == 2
    assert (run_row(database, stale)["status"], run_row(database, stale)["error_code"]) == (
        "failed",
        "RUN_INTERRUPTED",
    )
    assert (run_row(database, expired)["status"], run_row(database, expired)["error_code"]) == (
        "failed",
        "RUN_TIMED_OUT",
    )
    assert {(run.id, error.code, error.retryable) for run, error in fresh.handler.failed} == {
        (stale, "RUN_INTERRUPTED", True),
        (expired, "RUN_TIMED_OUT", True),
    }
    assert await fresh.runtime.worker.run_once() is True
    assert run_row(database, remaining)["status"] == "succeeded"
    assert await fresh.runtime.worker.recover() == 0


async def test_concurrent_recoveries_handle_each_run_once(database: Database, seed: Seed) -> None:
    rig = build_rig(database, seed)
    run_ids = [register(database, rig, work_request(seed, c)) for c in seed.conversations]
    for run_id in run_ids:
        set_run(database, run_id, created_at=rig.clock() - timedelta(hours=1))
    workers = [build_rig(database, seed, clock=rig.clock) for _ in range(3)]
    handled = await asyncio.gather(*(w.runtime.worker.recover() for w in workers))
    assert sum(handled) == len(run_ids)
    failed = [run.id for w in workers for run, _ in w.handler.failed]
    assert sorted(failed) == sorted(run_ids)
    for w in workers:
        await w.runtime.relay.flush()
    published = [e for w in workers for e in w.publisher.events if e.data["run"]["status"] == "failed"]
    assert len(published) == len(run_ids)


async def test_retried_runs_wait_from_the_retry_not_from_creation(database: Database, seed: Seed) -> None:
    rig = build_rig(database, seed, gateway=FakeLLM(failure_code="LLM_UNAVAILABLE"))
    run_id = register(database, rig, work_request(seed, seed.conversations[0]))
    await rig.runtime.worker.run_once()
    set_run(database, run_id, created_at=rig.clock() - timedelta(hours=1))
    with database.transaction() as session:
        rig.runtime.control.retry(session, run_id, seed.owner)
    assert await rig.runtime.worker.recover() == 0
    assert run_row(database, run_id)["status"] == "pending"


async def test_runs_without_a_handler_stay_pending_until_they_expire(database: Database, seed: Seed) -> None:
    rig = build_rig(database, seed)  # work handler only
    run_id = register(database, rig, summary_request(seed, seed.child))
    assert await rig.runtime.worker.run_once() is False
    assert run_row(database, run_id)["status"] == "pending"
    rig.clock.advance(FAST.max_pending_wait + timedelta(minutes=1))
    assert await rig.runtime.worker.recover() == 1
    assert run_row(database, run_id)["error_code"] == "RUN_TIMED_OUT"


# --- 7. ON-AC-08 credential ownership --------------------------------------------------------------


async def test_runs_use_only_the_requesters_credential(database: Database, seed: Seed) -> None:
    model = FakeLLM()
    rig = build_rig(database, seed, gateway=model)
    run_id = register(database, rig, work_request(seed, seed.conversations[0], seed.other))
    await rig.runtime.worker.run_once()
    assert run_row(database, run_id)["credential_account_id"] == seed.other
    assert [request.credential_account_id for request in model.calls] == [seed.other]


async def test_a_handler_requesting_another_key_never_reaches_the_model(
    database: Database, seed: Seed
) -> None:
    model = FakeLLM()
    handler = FakeRunPurposeHandler(credential_override=seed.owner)
    rig = build_rig(database, seed, gateway=model, handlers=[handler])
    run_id = register(database, rig, work_request(seed, seed.conversations[0], seed.other))
    await rig.runtime.worker.run_once()
    assert model.calls == ()
    row = run_row(database, run_id)
    assert (row["status"], row["error_code"]) == ("failed", "RUN_CREDENTIAL_MISMATCH")
    ((_, error),) = handler.failed
    assert (error.code, error.retryable) == ("RUN_CREDENTIAL_MISMATCH", False)


# --- 8. AC-17 input pinning ------------------------------------------------------------------------


def context(version: int) -> ConversationContext:
    resource = ResourceInput(
        UUID(int=100), UUID(int=100 + version), "skill", "스킬", f"지침 v{version}", None
    )
    result = ResultInput(UUID(int=200), UUID(int=200 + version), version, "결과", f"결론 v{version}")
    return ConversationContext((resource,), (result,))


async def test_new_versions_saved_during_a_run_do_not_change_its_input(
    database: Database, seed: Seed
) -> None:
    model = GatedLLM()
    rig = build_rig(database, seed, gateway=model)
    conversation = seed.conversations[0]
    rig.contexts.set_context(conversation, context(1))
    run_id = register(database, rig, work_request(seed, conversation))
    worker = asyncio.create_task(rig.runtime.worker.run_once())
    await asyncio.wait_for(model.started.wait(), 5)
    rig.contexts.set_context(conversation, context(2))
    model.release.set()
    await asyncio.wait_for(worker, 5)

    pinned = {
        "resource_revision_ids": [str(UUID(int=101))],
        "input_result_revision_ids": [str(UUID(int=201))],
    }
    snapshot = run_row(database, run_id)["input_snapshot"]
    assert {key: snapshot[key] for key in pinned} == pinned
    (request,) = model.calls
    assert request.context == context(1)
    ((completed_run, _),) = rig.handler.completed
    assert completed_run.input_snapshot.resource_revision_ids == (UUID(int=101),)


async def test_retry_pins_the_versions_current_at_the_new_claim(database: Database, seed: Seed) -> None:
    rig = build_rig(database, seed, gateway=ScriptedLLM(FakeLLM(failure_code="LLM_UNAVAILABLE"), FakeLLM()))
    conversation = seed.conversations[0]
    rig.contexts.set_context(conversation, context(1))
    run_id = register(database, rig, work_request(seed, conversation))
    await rig.runtime.worker.run_once()
    rig.contexts.set_context(conversation, context(2))
    with database.transaction() as session:
        rig.runtime.control.retry(session, run_id, seed.owner)
    await rig.runtime.worker.run_once()
    row = run_row(database, run_id)
    assert (row["status"], row["input_snapshot"]["resource_revision_ids"]) == (
        "succeeded",
        [str(UUID(int=102))],
    )


# --- long-running worker ---------------------------------------------------------------------------


async def test_running_worker_picks_up_a_committed_request_and_publishes(
    database: Database, seed: Seed
) -> None:
    rig = build_rig(database, seed, config=ExecutorConfig(poll_interval=timedelta(seconds=30), concurrency=2))
    loop_task = asyncio.create_task(rig.runtime.worker.run_forever())
    try:
        run_id = await asyncio.to_thread(register, database, rig, work_request(seed, seed.conversations[0]))
        await eventually(lambda: run_row(database, run_id)["status"] == "succeeded")
        await eventually(lambda: statuses(rig.publisher.events, run_id)[-1:] == ["succeeded"])
    finally:
        loop_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await loop_task
    assert statuses(rig.publisher.events, run_id) == ["pending", "running", "succeeded"]
    assert RunStatus(run_row(database, run_id)["status"]) == RunStatus.SUCCEEDED
    assert RunPurpose.WORK in rig.runtime.worker.purposes
