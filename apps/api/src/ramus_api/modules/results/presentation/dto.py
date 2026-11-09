"""Result DTOs: summaries, drafts, and approved versions (docs/contracts.md sections 2 and 3.2)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from ramus_api.shared.presentation.schemas import ApiRequest, ApiResponse, ErrorSummary

MAX_CONCLUSION_LENGTH = 20_000

DraftStatus = Literal["generating", "ready", "failed"]


class ResultDraft(ApiResponse):
    status: DraftStatus
    conclusion: str | None
    base_version: int = Field(description="Latest approved version; 0 when none exists.")
    run_id: UUID
    error: ErrorSummary | None
    updated_at: datetime


class ResultRevisionEntry(ApiResponse):
    id: UUID
    version: int
    saved_by: UUID
    created_at: datetime


class Result(ApiResponse):
    id: UUID
    project_id: UUID
    title: str
    source_conversation_id: UUID
    source_task_id: UUID
    latest_version: int | None
    latest_revision_id: UUID | None
    draft: ResultDraft | None
    revisions: list[ResultRevisionEntry]


class ResultRevisionSource(ApiResponse):
    conversation_id: UUID
    message_from_seq: int
    message_to_seq: int
    resource_revision_ids: list[UUID]
    input_result_revision_ids: list[UUID]
    run_id: UUID


class ResultRevision(ApiResponse):
    id: UUID
    result_id: UUID
    version: int
    title: str
    conclusion: str
    source: ResultRevisionSource
    saved_by: UUID
    created_at: datetime


class SaveResultRevisionRequest(ApiRequest):
    base_version: int = Field(ge=0, description="Version the edit started from; 0 when none exists.")
    conclusion: str = Field(min_length=1, max_length=MAX_CONCLUSION_LENGTH)


class ProjectResultSummary(ApiResponse):
    result_id: UUID
    title: str
    latest_version: int
    latest_revision_id: UUID
    source_conversation_title: str
    updated_at: datetime


class ProjectResultList(ApiResponse):
    items: list[ProjectResultSummary]
