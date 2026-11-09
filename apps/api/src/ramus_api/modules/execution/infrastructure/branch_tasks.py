"""Task creation and guarded projection of its current work run. No commits or publication here."""

from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from sqlalchemy import insert, or_, select, update
from sqlalchemy.orm import Session

from ramus_api.modules.execution.application.branch_ports import NewBranchTask
from ramus_api.modules.execution.domain.models import RunPurpose, RunStatus
from ramus_api.modules.execution.domain.state import RunState
from ramus_api.modules.execution.infrastructure.models import TaskRow
from ramus_api.modules.realtime.domain.events import EventName, ProjectEvent
from ramus_api.modules.results.application.task_results import TaskResultQuery


class SqlBranchTaskStore:
    def __init__(self, results: TaskResultQuery[Session]) -> None:
        self._results = results

    def create(self, session: Session, task: NewBranchTask) -> None:
        session.execute(insert(TaskRow).values(**asdict(task), status="pending"))

    def goal(self, session: Session, task_id: UUID) -> str:
        return session.execute(select(TaskRow.goal).where(TaskRow.id == task_id)).scalar_one()

    def project(self, session: Session, state: RunState, occurred_at: datetime) -> ProjectEvent | None:
        if state.purpose != RunPurpose.WORK or state.task_id is None:
            return None
        current = TaskRow.current_run_id == state.id
        if state.status == RunStatus.PENDING:
            current = or_(current, TaskRow.current_run_id.is_(None), TaskRow.status.in_(("ready", "failed", "cancelled")))
        row = session.execute(
            update(TaskRow)
            .where(
                TaskRow.id == state.task_id,
                TaskRow.child_conversation_id == state.conversation_id,
                current,
            )
            .values(
                current_run_id=state.id,
                status="ready" if state.status == RunStatus.SUCCEEDED else state.status.value,
                started_at=state.started_at,
                finished_at=state.finished_at,
                error_code=state.error_code,
                error_params=dict(state.error_params) if state.error_params is not None else None,
            )
            .returning(TaskRow.id, TaskRow.source_conversation_id, TaskRow.child_conversation_id, TaskRow.title, TaskRow.status)
        ).one_or_none()
        if row is None:
            return None
        return ProjectEvent(
            state.project_id,
            EventName.TASK_UPDATED,
            occurred_at,
            {
                "source_conversation_id": row.source_conversation_id,
                "task": {
                    "id": row.id,
                    "title": row.title,
                    "status": row.status,
                    "child_conversation_id": row.child_conversation_id,
                    "result_id": self._results.for_task(session, row.id),
                },
            },
        )
