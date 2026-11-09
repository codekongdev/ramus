"""Sharing DTOs: sending conclusions to conversations and the inputs they create (docs/contracts.md)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from ramus_api.modules.conversations.presentation.dto import MAX_CONVERSATION_TITLE_LENGTH
from ramus_api.modules.results.presentation.dto import ResultRevisionSource
from ramus_api.shared.presentation.schemas import ApiRequest, ApiResponse

MAX_SHARE_TARGETS = 20

ShareOutcome = Literal["linked", "replaced", "unchanged", "kept_newer"]
InputOrigin = Literal["share", "new_conversation"]


class ShareResultRevisionRequest(ApiRequest):
    # No minimum: an empty list is the business error SHARE_TARGET_INVALID (contracts 1.2), not INVALID_INPUT.
    conversation_ids: list[UUID] = Field(max_length=MAX_SHARE_TARGETS)


class ShareTargetOutcome(ApiResponse):
    conversation_id: UUID
    outcome: ShareOutcome


class ShareOutcomeList(ApiResponse):
    items: list[ShareTargetOutcome]


class ConversationInput(ApiResponse):
    id: UUID
    conversation_id: UUID
    result_id: UUID
    result_revision_id: UUID
    version: int
    title: str
    latest_version: int = Field(description="Latest source version visible to this account; pinned version when source access is restricted.")
    origin: InputOrigin
    created_by: UUID
    created_at: datetime


class ConversationInputDetail(ConversationInput):
    conclusion: str
    source: ResultRevisionSource


class ConversationInputList(ApiResponse):
    items: list[ConversationInput]


class CreateConversationFromResultRequest(ApiRequest):
    result_revision_id: UUID
    title: str = Field(min_length=1, max_length=MAX_CONVERSATION_TITLE_LENGTH)
