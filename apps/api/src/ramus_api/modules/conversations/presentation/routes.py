"""Authenticated conversation tree and server-authored message endpoints."""

from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Query

from ramus_api.container import AppContainer
from ramus_api.modules.access.presentation.current_account import AuthenticatedAccount, require_account
from ramus_api.modules.conversations.composition import CommittedEvents, build_conversation_service
from ramus_api.modules.conversations.domain.errors import ConversationNotFound
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
from ramus_api.shared.domain.errors import BusinessError
from ramus_api.shared.presentation.errors import http_error_code
from ramus_api.shared.presentation.idempotency import IdempotencyKey

SearchQuery = Annotated[str, Query(max_length=100, description="Title search text; empty lists everything.")]
AfterSeq = Annotated[int | None, Query(ge=0, description="Return messages after this sequence number.")]
PageSize = Annotated[int, Query(ge=1, le=MAX_MESSAGE_PAGE_SIZE)]


@contextmanager
def conversation_errors():
    try:
        yield
    except ConversationNotFound:
        code, message = http_error_code(404)
        raise BusinessError(code, message, status=404) from None


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["conversations"])
    CurrentAccount = Annotated[AuthenticatedAccount, Depends(require_account(container))]
    service = build_conversation_service(
        container, container.project_access, container.run_requester, container.run_reader,
        CommittedEvents(container),
    )

    @router.get(
        "/projects/{project_id}/conversations",
        response_model=ConversationList,
        operation_id="listConversations",
    )
    def list_conversations(project_id: UUID, account: CurrentAccount):
        with conversation_errors():
            return service.list_conversations(project_id, account.account_id)

    @router.post(
        "/projects/{project_id}/conversations",
        response_model=Conversation,
        operation_id="createConversation",
    )
    def create_conversation(
        project_id: UUID, body: CreateConversationRequest, idempotency_key: IdempotencyKey,
        account: CurrentAccount,
    ):
        with conversation_errors():
            return service.create_conversation(project_id, account.account_id, body.title, idempotency_key)

    @router.get(
        "/projects/{project_id}/conversations/search",
        response_model=ConversationList,
        operation_id="searchConversations",
    )
    def search_conversations(
        project_id: UUID, account: CurrentAccount, q: SearchQuery = "", exclude_id: UUID | None = None
    ):
        with conversation_errors():
            return service.list_conversations(project_id, account.account_id, q, exclude_id)

    @router.get(
        "/conversations/{conversation_id}",
        response_model=ConversationDetail,
        operation_id="getConversation",
    )
    def get_conversation(conversation_id: UUID, account: CurrentAccount):
        with conversation_errors():
            return service.get_conversation(conversation_id, account.account_id)

    @router.get(
        "/conversations/{conversation_id}/messages",
        response_model=MessageList,
        operation_id="listMessages",
    )
    def list_messages(
        conversation_id: UUID, account: CurrentAccount,
        after_seq: AfterSeq = None, limit: PageSize = DEFAULT_MESSAGE_PAGE_SIZE,
    ):
        with conversation_errors():
            return service.list_messages(conversation_id, account.account_id, after_seq, limit)

    @router.post(
        "/conversations/{conversation_id}/messages",
        response_model=PostMessageResponse,
        operation_id="postMessage",
    )
    def post_message(
        conversation_id: UUID, body: PostMessageRequest, idempotency_key: IdempotencyKey,
        account: CurrentAccount,
    ):
        with conversation_errors():
            return service.post_message(conversation_id, account.account_id, body.body, idempotency_key)

    app.include_router(router)
