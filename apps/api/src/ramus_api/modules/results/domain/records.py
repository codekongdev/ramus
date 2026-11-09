"""Framework-free result records. Drafts and immutable approved versions have separate lifecycles."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ramus_api.modules.execution.domain.models import ConversationContext


@dataclass(frozen=True)
class Source:
    conversation_id: UUID
    message_from_seq: int
    message_to_seq: int
    resource_revision_ids: tuple[UUID, ...]
    input_result_revision_ids: tuple[UUID, ...]
    run_id: UUID


@dataclass(frozen=True)
class Draft:
    status: str
    conclusion: str | None
    base_version: int
    run_id: UUID
    message_from_seq: int
    message_to_seq: int
    context: ConversationContext
    error_code: str | None
    updated_at: datetime


@dataclass(frozen=True)
class Revision:
    id: UUID
    result_id: UUID
    version: int
    title: str
    conclusion: str
    source: Source
    saved_by: UUID
    created_at: datetime


@dataclass(frozen=True)
class ResultRecord:
    id: UUID
    project_id: UUID
    source_conversation_id: UUID
    source_task_id: UUID
    title: str
    latest_revision_id: UUID | None
    latest_version: int
    draft: Draft | None
    revisions: tuple[Revision, ...]
