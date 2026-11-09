"""Results-owned query adapter; execution does not access result tables."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.results.infrastructure.models import ResultRow


class SqlTaskResultQuery:
    def for_task(self, session: Session, task_id: UUID) -> UUID | None:
        return session.execute(select(ResultRow.id).where(ResultRow.source_task_id == task_id)).scalar_one_or_none()
