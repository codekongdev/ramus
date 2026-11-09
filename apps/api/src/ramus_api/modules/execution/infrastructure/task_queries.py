"""Task DTO projection. Result lookup uses the results-owned public boundary."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.execution.application.errors import MESSAGES
from ramus_api.modules.execution.infrastructure.models import TaskRow
from ramus_api.modules.execution.presentation.dto import Task
from ramus_api.modules.results.application.task_results import TaskResultQuery
from ramus_api.shared.presentation.error_messages import message_for
from ramus_api.shared.presentation.schemas import ErrorSummary


class SqlTaskQueryStore:
    def __init__(self, results: TaskResultQuery[Session]) -> None:
        self._results = results

    def _response(self, session: Session, row: TaskRow) -> dict:
        error = None
        if row.error_code is not None:
            code = row.error_code if row.error_code in MESSAGES else "LLM_UNAVAILABLE"
            error = ErrorSummary(code=code, message=message_for(code))
        return Task(
            id=row.id, source_conversation_id=row.source_conversation_id,
            child_conversation_id=row.child_conversation_id, title=row.title, goal=row.goal,
            status=row.status, requested_by=row.requested_by,
            result_id=self._results.for_task(session, row.id), created_at=row.created_at,
            started_at=row.started_at, finished_at=row.finished_at, error=error,
        ).model_dump()

    def get(self, session: Session, task_id: UUID) -> dict | None:
        row = session.get(TaskRow, task_id)
        return None if row is None else self._response(session, row)

    def list_for_conversation(self, session: Session, conversation_id: UUID) -> list[dict]:
        rows = session.scalars(select(TaskRow).where(
            TaskRow.source_conversation_id == conversation_id,
        ).order_by(TaskRow.created_at, TaskRow.id))
        return [self._response(session, row) for row in rows]
