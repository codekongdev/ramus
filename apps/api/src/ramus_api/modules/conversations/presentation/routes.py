"""Conversation endpoints: tree, search, detail, and messages. Stubs until the conversations task."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, FastAPI, Query

from ramus_api.container import AppContainer
from ramus_api.modules.conversations.presentation.dto import (
    DEFAULT_MESSAGE_PAGE_SIZE,
    MAX_MESSAGE_PAGE_SIZE,
    Conversation,
    ConversationDetail,
    ConversationList,
    CreateConversationRequest,
    MessageList,
    PostMessageRequest,
    PostMessageResponse,
)
from ramus_api.shared.presentation.error_messages import not_implemented
from ramus_api.shared.presentation.idempotency import IdempotencyKey

SearchQuery = Annotated[str, Query(max_length=100, description="Title search text; empty lists everything.")]
AfterSeq = Annotated[int | None, Query(ge=0, description="Return messages after this sequence number.")]
PageSize = Annotated[int, Query(ge=1, le=MAX_MESSAGE_PAGE_SIZE)]


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["conversations"])

    @router.get(
        "/projects/{project_id}/conversations",
        response_model=ConversationList,
        operation_id="listConversations",
    )
    def list_conversations(project_id: UUID):
        raise not_implemented()

    @router.post(
        "/projects/{project_id}/conversations",
        response_model=Conversation,
        operation_id="createConversation",
    )
    def create_conversation(
        project_id: UUID, body: CreateConversationRequest, idempotency_key: IdempotencyKey
    ):
        raise not_implemented()

    @router.get(
        "/projects/{project_id}/conversations/search",
        response_model=ConversationList,
        operation_id="searchConversations",
    )
    def search_conversations(project_id: UUID, q: SearchQuery = "", exclude_id: UUID | None = None):
        raise not_implemented()

    @router.get(
        "/conversations/{conversation_id}",
        response_model=ConversationDetail,
        operation_id="getConversation",
    )
    def get_conversation(conversation_id: UUID):
        raise not_implemented()

    @router.get(
        "/conversations/{conversation_id}/messages",
        response_model=MessageList,
        operation_id="listMessages",
    )
    def list_messages(
        conversation_id: UUID, after_seq: AfterSeq = None, limit: PageSize = DEFAULT_MESSAGE_PAGE_SIZE
    ):
        raise not_implemented()

    @router.post(
        "/conversations/{conversation_id}/messages",
        response_model=PostMessageResponse,
        operation_id="postMessage",
    )
    def post_message(conversation_id: UUID, body: PostMessageRequest, idempotency_key: IdempotencyKey):
        raise not_implemented()

    app.include_router(router)
