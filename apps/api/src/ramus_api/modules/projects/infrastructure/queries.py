"""Project repository for the list shown after login."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.projects.domain.project import ProjectInfo
from ramus_api.modules.projects.infrastructure.models import ProjectRow


class SqlProjectRepository:
    def list_by_ids(self, transaction: Session, ids: list[UUID]) -> list[ProjectInfo]:
        rows = transaction.scalars(
            select(ProjectRow).where(ProjectRow.id.in_(ids)).order_by(ProjectRow.created_at, ProjectRow.id)
        )
        return [ProjectInfo(row.id, row.name, row.is_shared_sample) for row in rows]
