"""Results-owned example conclusions and maintenance operations."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ramus_api.modules.results.infrastructure.models import ResultDraftRow, ResultRevisionRow, ResultRow


class SampleResults:
    def add(
        self, session: Session, *, identifier: UUID, revision_id: UUID, project_id: UUID,
        conversation_id: UUID, task_id: UUID, title: str, conclusion: str, source: dict,
        author_id: UUID,
    ) -> None:
        session.add(ResultRow(
            id=identifier, project_id=project_id, source_conversation_id=conversation_id,
            source_task_id=task_id, title=title, latest_revision_id=revision_id, latest_version=1,
        ))
        session.flush()
        session.add(ResultRevisionRow(
            id=revision_id, result_id=identifier, version=1, title=title, conclusion=conclusion,
            source=source, saved_by=author_id,
        ))
        session.flush()

    def ids(self, session: Session, project_ids: tuple[UUID, ...]) -> tuple[UUID, ...]:
        return tuple(session.scalars(select(ResultRow.id).where(ResultRow.project_id.in_(project_ids))))

    def revision_ids(self, session: Session, project_ids: tuple[UUID, ...]) -> tuple[UUID, ...]:
        return tuple(session.scalars(select(ResultRevisionRow.id).join(
            ResultRow, ResultRevisionRow.result_id == ResultRow.id,
        ).where(ResultRow.project_id.in_(project_ids))))

    def clear(self, session: Session, project_ids: tuple[UUID, ...]) -> None:
        result_ids = select(ResultRow.id).where(ResultRow.project_id.in_(project_ids))
        session.execute(delete(ResultDraftRow).where(ResultDraftRow.result_id.in_(result_ids)))
        session.execute(delete(ResultRevisionRow).where(ResultRevisionRow.result_id.in_(result_ids)))
        session.execute(delete(ResultRow).where(ResultRow.project_id.in_(project_ids)))
