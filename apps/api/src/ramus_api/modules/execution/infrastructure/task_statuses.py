"""Execution-owned status projection for project relationship maps."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.execution.infrastructure.models import TaskRow


class SqlTaskStatuses:
    def by_ids(self, session: Session, task_ids: tuple[UUID, ...]) -> dict[UUID, str]:
        return dict(session.execute(select(TaskRow.id, TaskRow.status).where(TaskRow.id.in_(task_ids))).all())
