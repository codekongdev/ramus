"""API DTOs are constructed at the boundary, never returned as ORM rows."""

from dataclasses import asdict

from ramus_api.modules.results.domain.records import ResultRecord, Revision
from ramus_api.modules.results.presentation.dto import (
    Result,
    ResultDraft,
    ResultRevision,
    ResultRevisionEntry,
)
from ramus_api.shared.presentation.error_messages import message_for
from ramus_api.shared.presentation.schemas import ErrorSummary


def result_dto(record: ResultRecord) -> Result:
    draft = record.draft
    return Result(
        id=record.id, project_id=record.project_id, title=record.title,
        source_conversation_id=record.source_conversation_id, source_task_id=record.source_task_id,
        latest_version=record.latest_version or None, latest_revision_id=record.latest_revision_id,
        draft=None if draft is None else ResultDraft(
            status=draft.status, conclusion=draft.conclusion, base_version=draft.base_version,
            run_id=draft.run_id, updated_at=draft.updated_at,
            error=ErrorSummary(code=draft.error_code, message=message_for(draft.error_code)) if draft.error_code else None,
        ),
        revisions=[ResultRevisionEntry(id=item.id, version=item.version, saved_by=item.saved_by,
                                       created_at=item.created_at) for item in record.revisions],
    )


def revision_dto(record: Revision) -> ResultRevision:
    return ResultRevision(**asdict(record))
