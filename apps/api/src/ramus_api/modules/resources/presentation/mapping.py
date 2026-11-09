"""Use-case results -> response DTOs, and domain rule errors -> the API error envelope.

Kept separate from ``routes.py`` so the routes stay thin once the current-account dependency exists.
"""

from __future__ import annotations

from ramus_api.modules.resources.application.ports import AppliedRecord, ResourceHistory, RevisionRecord
from ramus_api.modules.resources.application.use_cases import SearchHit
from ramus_api.modules.resources.domain.rules import (
    FILE_TYPE_UNSUPPORTED,
    INVALID_INPUT,
    NOT_FOUND,
    VERSION_CONFLICT,
    ResourceRuleError,
)
from ramus_api.modules.resources.presentation.dto import (
    AppliedResource,
    AppliedResourceList,
    AppliedRevisionRef,
    ResourceDetail,
    ResourceLatest,
    ResourceRevision,
    ResourceRevisionEntry,
    ResourceSummary,
    ResourceSummaryList,
)
from ramus_api.shared.domain import BusinessError
from ramus_api.shared.presentation.error_messages import message_for, register_error_messages
from ramus_api.shared.presentation.errors import HTTP_ERRORS, INVALID_INPUT_MESSAGE

register_error_messages(
    {
        FILE_TYPE_UNSUPPORTED: ".md 또는 .txt 형식의 UTF-8 텍스트 파일만 올릴 수 있습니다.",
        VERSION_CONFLICT: "다른 사람이 먼저 새 버전을 저장했습니다. 최신 내용을 확인한 뒤 다시 저장해 주세요.",
    }
)

_STATUS = {INVALID_INPUT: 422, FILE_TYPE_UNSUPPORTED: 422, NOT_FOUND: 404, VERSION_CONFLICT: 409}


def to_business_error(error: ResourceRuleError) -> BusinessError:
    status = _STATUS[error.code]
    if error.code == INVALID_INPUT:
        message = INVALID_INPUT_MESSAGE
    elif error.code == NOT_FOUND:
        message = HTTP_ERRORS[404][1]
    else:
        message = message_for(error.code)
    # NOT_FOUND carries no details so a non-member cannot tell "missing" from "forbidden".
    return BusinessError(
        error.code, message, status=status, details=None if error.code == NOT_FOUND else error.details
    )


def revision_dto(record: RevisionRecord) -> ResourceRevision:
    content = record.content
    return ResourceRevision(
        id=record.id,
        resource_id=record.resource_id,
        number=record.number,
        name=content.name,
        description=content.description,
        instructions=content.instructions,
        content=content.content,
        file_name=content.file_name,
        created_by=record.created_by,
        created_at=record.created_at,
    )


def resource_detail(history: ResourceHistory, selected: RevisionRecord | None = None) -> ResourceDetail:
    resource = history.resource
    return ResourceDetail(
        id=resource.id,
        kind=resource.kind.value,
        latest_revision_id=resource.latest.id,
        revisions=[
            ResourceRevisionEntry(
                id=e.id, number=e.number, name=e.name, created_by=e.created_by, created_at=e.created_at
            )
            for e in history.revisions
        ],
        revision=revision_dto(selected or resource.latest),
    )


def summary_list(hits: tuple[SearchHit, ...]) -> ResourceSummaryList:
    return ResourceSummaryList(
        items=[
            ResourceSummary(
                id=hit.resource.id,
                kind=hit.resource.kind.value,
                latest=ResourceLatest(
                    revision_id=hit.resource.latest.id,
                    number=hit.resource.latest.number,
                    name=hit.resource.latest.content.name,
                    description=hit.resource.latest.content.description,
                ),
                applied=None
                if hit.applied is None
                else AppliedRevisionRef(revision_id=hit.applied.revision_id, number=hit.applied.number),
            )
            for hit in hits
        ]
    )


def applied_list(items: tuple[AppliedRecord, ...]) -> AppliedResourceList:
    return AppliedResourceList(
        items=[
            AppliedResource(
                resource_id=i.resource_id,
                revision_id=i.revision_id,
                number=i.number,
                name=i.name,
                kind=i.kind.value,
            )
            for i in items
        ]
    )
