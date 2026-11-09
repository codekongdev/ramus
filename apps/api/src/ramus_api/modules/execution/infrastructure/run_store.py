"""SQL implementation of ``RunStore``. Every transition is a conditional UPDATE ... RETURNING."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Executable, Row, Select, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ramus_api.modules.execution.domain.errors import ActiveRunConflict
from ramus_api.modules.execution.domain.models import RunInputSnapshot, RunRequest, RunStatus
from ramus_api.modules.execution.domain.snapshot import EMPTY_SNAPSHOT, snapshot_from_json, snapshot_to_json
from ramus_api.modules.execution.domain.state import RunFailure, RunState
from ramus_api.modules.execution.infrastructure.models import RunRow

run = RunRow.__table__

# Partial unique indexes from the P0-A2 migration. Only these mean "another active run exists".
ACTIVE_RUN_INDEXES = frozenset({"uq_run_active_work_conversation", "uq_run_active_summary_target"})


def _state(row: Row[Any] | Mapping[str, Any]) -> RunState:
    values = dict(row._mapping) if isinstance(row, Row) else dict(row)
    return RunState(
        id=values["id"],
        project_id=values["project_id"],
        conversation_id=values["conversation_id"],
        task_id=values["task_id"],
        purpose=values["purpose"],
        target_id=values["target_id"],
        status=values["status"],
        requested_by=values["requested_by"],
        credential_account_id=values["credential_account_id"],
        input_snapshot=snapshot_from_json(values["input_snapshot"]),
        attempt=values["attempt"],
        error_code=values["error_code"],
        error_params=values["error_params"],
        heartbeat_at=values["heartbeat_at"],
        started_at=values["started_at"],
        finished_at=values["finished_at"],
        created_at=values["created_at"],
    )


def _constraint_name(error: IntegrityError) -> str | None:
    diag = getattr(error.orig, "diag", None)
    return getattr(diag, "constraint_name", None)


def _guarded(session: Session, statement: Executable) -> RunState | None:
    """Runs a statement that may hit an active-run index inside a savepoint."""
    try:
        with session.begin_nested():
            row = session.execute(statement).one_or_none()
    except IntegrityError as error:
        if _constraint_name(error) in ACTIVE_RUN_INDEXES:
            raise ActiveRunConflict() from None
        raise
    return None if row is None else _state(row)


def _transition(
    session: Session, run_id: UUID, *conditions: ColumnElement[bool], **values: Any
) -> RunState | None:
    statement = update(run).where(run.c.id == run_id, *conditions).values(**values).returning(run)
    row = session.execute(statement).one_or_none()
    return None if row is None else _state(row)


def _lock_one(session: Session, query: Select[Any]) -> RunState | None:
    row = session.execute(query.limit(1).with_for_update(skip_locked=True)).one_or_none()
    return None if row is None else _state(row)


def _failure_values(failure: RunFailure | None) -> dict[str, Any]:
    if failure is None:
        return {"error_code": None, "error_params": None}
    params = dict(failure.params) if failure.params is not None else None
    return {"error_code": failure.code, "error_params": params}


class SqlRunStore:
    def insert(
        self,
        session: Session,
        run_id: UUID,
        request: RunRequest,
        credential_account_id: UUID,
        snapshot: RunInputSnapshot,
    ) -> RunState:
        statement = (
            insert(run)
            .values(
                id=run_id,
                project_id=request.project_id,
                conversation_id=request.conversation_id,
                task_id=request.task_id,
                purpose=request.purpose.value,
                target_id=request.target_id,
                status=RunStatus.PENDING.value,
                requested_by=request.requested_by,
                credential_account_id=credential_account_id,
                input_snapshot=snapshot_to_json(snapshot),
                attempt=1,
            )
            .returning(run)
        )
        state = _guarded(session, statement)
        if state is None:
            raise RuntimeError("INSERT ... RETURNING produced no row")
        return state

    def lock(self, session: Session, run_id: UUID) -> RunState | None:
        row = session.execute(select(run).where(run.c.id == run_id).with_for_update()).one_or_none()
        return None if row is None else _state(row)

    def claim_next(self, session: Session, purposes: frozenset[str], now: datetime) -> RunState | None:
        if not purposes:
            return None
        query = (
            select(run.c.id)
            .where(run.c.status == RunStatus.PENDING.value, run.c.purpose.in_(sorted(purposes)))
            .order_by(run.c.created_at, run.c.id)
        )
        run_id = session.execute(query.limit(1).with_for_update(skip_locked=True)).scalar_one_or_none()
        if run_id is None:
            return None
        return _transition(
            session,
            run_id,
            run.c.status == RunStatus.PENDING.value,
            status=RunStatus.RUNNING.value,
            started_at=now,
            heartbeat_at=now,
        )

    def save_snapshot(
        self, session: Session, run_id: UUID, attempt: int, snapshot: RunInputSnapshot
    ) -> RunState | None:
        return _transition(
            session,
            run_id,
            run.c.attempt == attempt,
            run.c.status == RunStatus.RUNNING.value,
            input_snapshot=snapshot_to_json(snapshot),
        )

    def heartbeat(self, session: Session, run_id: UUID, attempt: int, now: datetime) -> bool:
        statement = (
            update(run)
            .where(run.c.id == run_id, run.c.attempt == attempt, run.c.status == RunStatus.RUNNING.value)
            .values(heartbeat_at=now)
            .returning(run.c.id)
        )
        return session.execute(statement).one_or_none() is not None

    def finish(
        self,
        session: Session,
        run_id: UUID,
        attempt: int,
        expected: RunStatus,
        outcome: RunStatus,
        now: datetime,
        failure: RunFailure | None,
    ) -> RunState | None:
        return _transition(
            session,
            run_id,
            run.c.attempt == attempt,
            run.c.status == expected.value,
            status=outcome.value,
            finished_at=now,
            **_failure_values(failure),
        )

    def cancel(self, session: Session, run_id: UUID, now: datetime) -> RunState | None:
        active = (RunStatus.PENDING.value, RunStatus.RUNNING.value)
        return _transition(
            session, run_id, run.c.status.in_(active), status=RunStatus.CANCELLED.value, finished_at=now
        )

    def requeue(self, session: Session, run_id: UUID, now: datetime) -> RunState | None:
        """``heartbeat_at`` of a pending run marks when it was queued again (see ``lock_expired_pending``)."""
        statement = (
            update(run)
            .where(run.c.id == run_id, run.c.status.in_((RunStatus.FAILED.value, RunStatus.CANCELLED.value)))
            .values(
                status=RunStatus.PENDING.value,
                attempt=run.c.attempt + 1,
                input_snapshot=snapshot_to_json(EMPTY_SNAPSHOT),
                heartbeat_at=now,
                started_at=None,
                finished_at=None,
                **_failure_values(None),
            )
            .returning(run)
        )
        return _guarded(session, statement)

    def lock_stale_running(self, session: Session, heartbeat_before: datetime) -> RunState | None:
        query = (
            select(run)
            .where(run.c.status == RunStatus.RUNNING.value, run.c.heartbeat_at < heartbeat_before)
            .order_by(run.c.heartbeat_at, run.c.id)
        )
        return _lock_one(session, query)

    def lock_expired_pending(self, session: Session, queued_before: datetime) -> RunState | None:
        queued_at = func.coalesce(run.c.heartbeat_at, run.c.created_at)
        query = (
            select(run)
            .where(run.c.status == RunStatus.PENDING.value, queued_at < queued_before)
            .order_by(queued_at, run.c.id)
        )
        return _lock_one(session, query)
