"""Execution-owned implementation of the summary task read boundary."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.execution.application.summary_tasks import SummaryTask
from ramus_api.modules.execution.infrastructure.models import TaskRow


class SqlSummaryTaskReader:
    def get(self, session: Session, task_id: UUID, *, lock: bool = False) -> SummaryTask | None:
        query = select(TaskRow).where(TaskRow.id == task_id)
        if lock:
            query = query.with_for_update()
        row = session.scalar(query)
        return None if row is None else SummaryTask(row.id, row.child_conversation_id, row.title, row.status)
