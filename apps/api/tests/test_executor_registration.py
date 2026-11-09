"""Registration, cancel, retry and post-commit events against a migrated PostgreSQL database."""

import threading
from uuid import UUID, uuid4

import pytest
from executor_harness import (
    Rig,
    Seed,
    build_rig,
    register,
    run_row,
    seed_rows,
    statuses,
    summary_request,
    wait_for_lock_waiter,
    work_request,
)
from sqlalchemy import func, select, text

from ramus_api.modules.execution.domain.models import RunStatus
from ramus_api.modules.execution.infrastructure.commit_hooks import SqlAlchemyTransactionHooks
from ramus_api.modules.execution.infrastructure.models import RunRow
from ramus_api.shared.domain.errors import BusinessError
from ramus_api.shared.infrastructure.database import Database

pytestmark = pytest.mark.integration


@pytest.fixture
def seed(database: Database) -> Seed:
    return seed_rows(database)


@pytest.fixture
def rig(database: Database, seed: Seed) -> Rig:
    return build_rig(database, seed)


def active_runs(database: Database, **where: UUID) -> list[dict]:
    with database.transaction() as session:
        query = select(RunRow.__table__).where(RunRow.status.in_(["pending", "running"]))
        for column, value in where.items():
            query = query.where(getattr(RunRow, column) == value)
        return [dict(row) for row in session.execute(query).mappings()]


# --- 1. concurrent registration (ON-AC-09) ---------------------------------------------------------


@pytest.mark.parametrize("purpose", ["work", "summary"])
def test_concurrent_requests_for_one_target_leave_exactly_one_pending(
    database: Database, seed: Seed, rig: Rig, purpose: str
) -> None:
    make = work_request if purpose == "work" else summary_request
    first_request = make(seed, seed.conversations[0], seed.owner)
    # Summary uniqueness is per target, so the second request may even come from another conversation.
    second_request = make(seed, seed.conversations[0 if purpose == "work" else 1], seed.other)
    inserted, outcome = threading.Event(), {}

    def first() -> None:
        with database.transaction() as session:
            outcome["first"] = rig.runtime.requester.request(session, first_request)
            inserted.set()
            wait_for_lock_waiter(database)  # the second insert now blocks on the unique index

    def second() -> None:
        assert inserted.wait(5)
        with database.transaction() as session:
            with pytest.raises(BusinessError) as caught:
                rig.runtime.requester.request(session, second_request)
            outcome["error"] = (caught.value.code, caught.value.status)
            # The caller's transaction survives the rejected insert.
            outcome["other"] = rig.runtime.requester.request(
                session, work_request(seed, seed.conversations[2], seed.other)
            )

    threads = [threading.Thread(target=first), threading.Thread(target=second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert outcome["error"] == ("ACTIVE_RUN_EXISTS", 409)
    target = (
        {"target_id": seed.result} if purpose == "summary" else {"conversation_id": seed.conversations[0]}
    )
    rows = active_runs(database, **target)
    assert [(row["id"], row["requested_by"]) for row in rows] == [(outcome["first"].run_id, seed.owner)]
    assert run_row(database, outcome["other"].run_id)["status"] == "pending"


def test_runs_for_different_conversations_register_concurrently(
    database: Database, seed: Seed, rig: Rig
) -> None:
    barrier, refs = threading.Barrier(3), []

    def request(conversation: UUID) -> None:
        with database.transaction() as session:
            barrier.wait(5)
            refs.append(rig.runtime.requester.request(session, work_request(seed, conversation)))

    threads = [threading.Thread(target=request, args=(c,)) for c in seed.conversations[:3]]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert len(refs) == 3 and {ref.status for ref in refs} == {RunStatus.PENDING}
    assert len(active_runs(database, project_id=seed.project)) == 3


def test_registration_stores_requester_credential_and_an_empty_snapshot(
    database: Database, seed: Seed, rig: Rig
) -> None:
    run_id = register(database, rig, work_request(seed, seed.conversations[0], seed.other))
    row = run_row(database, run_id)
    assert (row["requested_by"], row["credential_account_id"], row["attempt"]) == (seed.other, seed.other, 1)
    assert row["input_snapshot"] == {
        "message_from_seq": None,
        "message_to_seq": None,
        "resource_revision_ids": [],
        "input_result_revision_ids": [],
    }
    assert (row["error_code"], row["started_at"], row["heartbeat_at"]) == (None, None, None)


def test_request_without_ai_connection_is_rejected_and_stores_nothing(
    database: Database, seed: Seed, rig: Rig
) -> None:
    rig.connections.set_connected(seed.other, False)
    with database.transaction() as session:
        with pytest.raises(BusinessError) as caught:
            rig.runtime.requester.request(session, work_request(seed, seed.conversations[0], seed.other))
    assert (caught.value.code, caught.value.status) == ("AI_CONNECTION_REQUIRED", 409)
    assert caught.value.message == "AI 연결을 먼저 설정해 주세요."
    assert active_runs(database, project_id=seed.project) == []


def test_other_integrity_errors_are_not_reported_as_active_runs(
    database: Database, seed: Seed, rig: Rig
) -> None:
    missing_conversation = work_request(seed, uuid4())
    with pytest.raises(Exception) as caught:
        with database.transaction() as session:
            rig.runtime.requester.request(session, missing_conversation)
    assert not isinstance(caught.value, BusinessError)


# --- 9. cancel and retry ---------------------------------------------------------------------------


def call(database: Database, action, *args):
    with database.transaction() as session:
        return action(session, *args)


def error_of(database: Database, action, *args) -> tuple[str, int]:
    with pytest.raises(BusinessError) as caught:
        call(database, action, *args)
    return caught.value.code, caught.value.status


def test_cancel_and_retry_are_limited_to_the_requester_and_valid_states(
    database: Database, seed: Seed, rig: Rig
) -> None:
    control = rig.runtime.control
    run_id = register(database, rig, work_request(seed, seed.conversations[0]))
    assert error_of(database, control.cancel, run_id, seed.other) == ("FORBIDDEN", 403)
    assert error_of(database, control.retry, run_id, seed.owner) == ("RUN_NOT_RETRYABLE", 409)
    assert error_of(database, control.cancel, uuid4(), seed.owner) == ("NOT_FOUND", 404)

    cancelled = call(database, control.cancel, run_id, seed.owner)
    assert cancelled.status == RunStatus.CANCELLED and cancelled.finished_at is not None
    assert error_of(database, control.cancel, run_id, seed.owner) == ("RUN_NOT_CANCELLABLE", 409)
    assert error_of(database, control.retry, run_id, seed.other) == ("FORBIDDEN", 403)

    blocker = register(database, rig, work_request(seed, seed.conversations[0], seed.other))
    with database.transaction() as session:
        with pytest.raises(BusinessError) as caught:
            control.retry(session, run_id, seed.owner)
        assert caught.value.code == "ACTIVE_RUN_EXISTS"
        session.execute(text("SELECT 1"))  # still usable
    call(database, control.cancel, blocker, seed.other)

    rig.connections.set_connected(seed.owner, False)
    assert error_of(database, control.retry, run_id, seed.owner) == ("AI_CONNECTION_REQUIRED", 409)
    rig.connections.set_connected(seed.owner, True)

    retried = call(database, control.retry, run_id, seed.owner)
    row = run_row(database, run_id)
    assert (retried.status, retried.attempt) == (RunStatus.PENDING, 2)
    assert (row["status"], row["attempt"], row["finished_at"], row["error_code"]) == (
        "pending",
        2,
        None,
        None,
    )


async def test_events_follow_commits_in_order(database: Database, seed: Seed, rig: Rig) -> None:
    control = rig.runtime.control
    run_id = register(database, rig, work_request(seed, seed.conversations[0]))
    call(database, control.cancel, run_id, seed.owner)
    call(database, control.retry, run_id, seed.owner)
    await rig.runtime.relay.flush()
    assert statuses(rig.publisher.events, run_id) == ["pending", "cancelled", "pending"]


# --- 10. events are post-commit and allowlisted ----------------------------------------------------


async def test_rolled_back_registration_publishes_nothing(database: Database, seed: Seed, rig: Rig) -> None:
    with pytest.raises(RuntimeError):
        with database.transaction() as session:
            rig.runtime.requester.request(session, work_request(seed, seed.conversations[0]))
            raise RuntimeError("caller failed after registering")
    with database.transaction() as session:
        savepoint = session.begin_nested()
        rig.runtime.requester.request(session, work_request(seed, seed.conversations[1]))
        savepoint.rollback()
    await rig.runtime.relay.flush()
    assert rig.publisher.events == ()
    with database.transaction() as session:
        query = select(func.count()).select_from(RunRow).where(RunRow.project_id == seed.project)
        assert session.execute(query).scalar_one() == 1  # only the seed's root run


async def test_event_data_has_only_contract_fields(database: Database, seed: Seed, rig: Rig) -> None:
    run_id = register(database, rig, work_request(seed, seed.conversations[0]))
    await rig.runtime.relay.flush()
    (event,) = rig.publisher.events
    assert event.project_id == seed.project
    assert dict(event.data) == {
        "conversation_id": seed.conversations[0],
        "run": {
            "id": run_id,
            "purpose": "work",
            "status": "pending",
            "task_id": None,
            "requested_by": seed.owner,
        },
    }


def test_commit_hooks_run_once_after_the_outermost_commit(database: Database, caplog) -> None:
    hooks, seen = SqlAlchemyTransactionHooks(), []
    with database.transaction() as session:
        with hooks.savepoint(session):
            hooks.after_commit(session, lambda: seen.append("released savepoint"))
        hooks.after_commit(session, lambda: 1 / 0)
        hooks.after_commit(session, lambda: seen.append("outer"))
        assert seen == []
    assert seen == ["released savepoint", "outer"]
    assert "ZeroDivisionError" in caplog.text
    with database.transaction() as session:
        session.execute(text("SELECT 1"))
    assert seen == ["released savepoint", "outer"]  # callbacks never run twice


def test_commit_hooks_drop_callbacks_of_a_rolled_back_savepoint(database: Database) -> None:
    hooks, seen = SqlAlchemyTransactionHooks(), []
    with database.transaction() as session:
        with pytest.raises(ValueError):
            with hooks.savepoint(session):
                hooks.after_commit(session, lambda: seen.append("inner"))
                raise ValueError("inner work failed")
        hooks.after_commit(session, lambda: seen.append("outer"))
    assert seen == ["outer"]
