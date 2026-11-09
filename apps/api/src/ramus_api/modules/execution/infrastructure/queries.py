"""Public run query adapter; conversation code never reads execution tables itself."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.execution.application.errors import MESSAGES
from ramus_api.modules.execution.infrastructure.models import RunRow
from ramus_api.modules.execution.presentation.dto import Run
from ramus_api.shared.presentation.error_messages import message_for
from ramus_api.shared.presentation.schemas import ErrorSummary


def _response(row: RunRow) -> dict:
    error = None
    if row.error_code is not None:
        code = row.error_code if row.error_code in MESSAGES else "LLM_UNAVAILABLE"
        error = ErrorSummary(code=code, message=message_for(code))
    return Run(
        id=row.id, conversation_id=row.conversation_id, task_id=row.task_id,
        purpose=row.purpose, status=row.status, requested_by=row.requested_by,
        created_at=row.created_at, started_at=row.started_at, finished_at=row.finished_at,
        error=error,
    ).model_dump(mode="json")


class SqlRunReader:
    def active_run(self, session: Session, conversation_id: UUID) -> dict | None:
        row = session.scalar(select(RunRow).where(
            RunRow.conversation_id == conversation_id,
            RunRow.purpose == "work", RunRow.status.in_(("pending", "running")),
        ))
        return None if row is None else _response(row)

    def get_run(self, session: Session, run_id: UUID) -> dict:
        row = session.get(RunRow, run_id)
        if row is None:
            raise LookupError("Registered run was not found")
        return _response(row)
