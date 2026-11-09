"""Execution-owned task projections; other modules are read through their public ports."""

from dataclasses import fields
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.execution.application.tasks import TaskRecord
from ramus_api.modules.execution.infrastructure.models import RunRow, TaskRow
from ramus_api.modules.results.application.task_results import TaskResultQuery


class SqlTaskRepository:
    def __init__(self, results: TaskResultQuery[Session]) -> None:
        self._results = results

    def _record(self, session: Session, row: TaskRow) -> TaskRecord:
        values = {field.name: getattr(row, field.name) for field in fields(TaskRecord) if field.name != "result_id"}
        return TaskRecord(**values, result_id=self._results.for_task(session, row.id))

    def get(self, session: Session, task_id: UUID) -> TaskRecord | None:
        row = session.scalar(select(TaskRow).where(TaskRow.id == task_id).execution_options(populate_existing=True))
        return None if row is None else self._record(session, row)

    def list_for_conversation(self, session: Session, conversation_id: UUID) -> tuple[TaskRecord, ...]:
        rows = session.scalars(
            select(TaskRow).where(TaskRow.source_conversation_id == conversation_id)
            .order_by(TaskRow.created_at, TaskRow.ordinal, TaskRow.id)
        )
        return tuple(self._record(session, row) for row in rows)

    def lock_current_work_run(self, session: Session, task: TaskRecord) -> bool:
        if task.current_run_id is None:
            return False
        # Do not lock Task before a retry obtains the active-run unique-index lock: a concurrent
        # new request inserts its Run before projecting Task, so doing so would form a deadlock.
        run_id = session.scalar(select(RunRow.id).where(
            RunRow.id == task.current_run_id,
            RunRow.task_id == task.id,
            RunRow.conversation_id == task.child_conversation_id,
            RunRow.purpose == "work",
        ).with_for_update())
        if run_id is None:
            return False
        current_run_id = session.scalar(select(TaskRow.current_run_id).where(TaskRow.id == task.id))
        return current_run_id == run_id

    def lock_current_task(self, session: Session, task: TaskRecord) -> bool:
        current_run_id = session.scalar(select(TaskRow.current_run_id).where(TaskRow.id == task.id).with_for_update())
        return current_run_id == task.current_run_id
