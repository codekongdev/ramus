"""Supported results queries and offline sample maintenance."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.results.application.approved import ApprovedConclusion as ApprovedConclusion
from ramus_api.modules.results.domain.records import ResultRecord, Revision
from ramus_api.modules.results.infrastructure.approved import (
    SqlApprovedConclusionReader as SqlApprovedConclusionReader,
)
from ramus_api.modules.results.infrastructure.models import ResultRow
from ramus_api.modules.results.infrastructure.repository import SqlResultRepository
from ramus_api.modules.results.infrastructure.sample import SampleResults as SampleResults

__all__ = ["ApprovedConclusion", "ResultReader", "ResultRecord", "Revision", "SampleResults", "SqlApprovedConclusionReader"]


class ResultReader:
    """Supported read-only results adapter for sharing and other module composition."""

    def __init__(self) -> None:
        self._repository = SqlResultRepository()

    def get(self, session: Session, result_id: UUID, *, lock: bool = False) -> ResultRecord | None:
        return self._repository.get(session, result_id, lock=lock)

    def revision(self, session: Session, revision_id: UUID) -> Revision | None:
        return self._repository.revision(session, revision_id)

    def source_conversations(self, session: Session, result_ids: tuple[UUID, ...]) -> dict[UUID, UUID]:
        return dict(session.execute(select(ResultRow.id, ResultRow.source_conversation_id).where(
            ResultRow.id.in_(result_ids),
        )).all())

    def latest_versions(self, session: Session, result_ids: tuple[UUID, ...]) -> dict[UUID, int]:
        return dict(session.execute(select(ResultRow.id, ResultRow.latest_version).where(
            ResultRow.id.in_(result_ids),
        )).all())
