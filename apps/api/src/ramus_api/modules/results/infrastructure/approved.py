"""Results-owned read boundary used when a saved conclusion becomes another conversation's input."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.results.application.approved import ApprovedConclusion
from ramus_api.modules.results.infrastructure.models import ResultRevisionRow, ResultRow


class SqlApprovedConclusionReader:
    def get(self, session: Session, revision_id: UUID) -> ApprovedConclusion | None:
        record = session.execute(
            select(ResultRevisionRow, ResultRow)
            .join(ResultRow, ResultRow.id == ResultRevisionRow.result_id)
            .where(ResultRevisionRow.id == revision_id)
        ).one_or_none()
        if record is None:
            return None
        revision, result = record
        return ApprovedConclusion(
            revision.id, result.id, result.project_id, revision.version, result.latest_version,
            revision.title, revision.conclusion, dict(revision.source),
        )
