"""Conversation DTOs: conversations and messages (docs/contracts.md sections 2 and 3.1)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from ramus_api.modules.conversations.domain.views import validate_text
from ramus_api.modules.execution.presentation.dto import Run
from ramus_api.shared.presentation.schemas import ApiRequest, ApiResponse

MAX_CONVERSATION_TITLE_LENGTH = 100
MAX_MESSAGE_BODY_LENGTH = 20_000
DEFAULT_MESSAGE_PAGE_SIZE = 100
MAX_MESSAGE_PAGE_SIZE = 200

AuthorKind = Literal["human", "ai", "system"]


class Conversation(ApiResponse):
    id: UUID
    project_id: UUID
    parent_id: UUID | None
    task_id: UUID | None
    title: str
    path: list[str] = Field(description="Titles of the ancestor conversations; tells same-titled ones apart.")
    created_by: UUID
    created_at: datetime


class ConversationDetail(Conversation):
    active_run: Run | None


class ConversationList(ApiResponse):
    items: list[Conversation]


class CreateConversationRequest(ApiRequest):
    title: str = Field(min_length=1, max_length=MAX_CONVERSATION_TITLE_LENGTH)

    @field_validator("title")
    @classmethod
    def meaningful_title(cls, value: str) -> str:
        return validate_text(value, MAX_CONVERSATION_TITLE_LENGTH)


class MessageAuthor(ApiResponse):
    kind: AuthorKind
    account_id: UUID | None
    display_name: str


class Message(ApiResponse):
    id: UUID
    conversation_id: UUID
    seq: int
    author: MessageAuthor
    body: str
    requested_by: UUID | None
    run_id: UUID | None
    is_example: bool
    created_at: datetime


class MessageList(ApiResponse):
    items: list[Message]
    next_after_seq: int | None


class PostMessageRequest(ApiRequest):
    body: str = Field(min_length=1, max_length=MAX_MESSAGE_BODY_LENGTH)

    @field_validator("body")
    @classmethod
    def meaningful_body(cls, value: str) -> str:
        return validate_text(value, MAX_MESSAGE_BODY_LENGTH)


class PostMessageResponse(ApiResponse):
    message: Message
    run: Run | None
