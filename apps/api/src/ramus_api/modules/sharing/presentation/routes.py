"""Sharing endpoints: send a conclusion version to conversations, list inputs, start from a result. Stubs."""

from uuid import UUID

from fastapi import APIRouter, FastAPI

from ramus_api.container import AppContainer
from ramus_api.modules.conversations.presentation.dto import Conversation
from ramus_api.modules.sharing.presentation.dto import (
    ConversationInputList,
    CreateConversationFromResultRequest,
    ShareOutcomeList,
    ShareResultRevisionRequest,
)
from ramus_api.shared.presentation.error_messages import not_implemented
from ramus_api.shared.presentation.idempotency import IdempotencyKey


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["sharing"])

    @router.post(
        "/result-revisions/{result_revision_id}/shares",
        response_model=ShareOutcomeList,
        operation_id="shareResultRevision",
    )
    def share_result_revision(
        result_revision_id: UUID, body: ShareResultRevisionRequest, idempotency_key: IdempotencyKey
    ):
        raise not_implemented()

    @router.get(
        "/conversations/{conversation_id}/inputs",
        response_model=ConversationInputList,
        operation_id="listConversationInputs",
    )
    def list_conversation_inputs(conversation_id: UUID):
        raise not_implemented()

    @router.post(
        "/projects/{project_id}/conversations/from-result",
        response_model=Conversation,
        operation_id="createConversationFromResult",
    )
    def create_conversation_from_result(
        project_id: UUID, body: CreateConversationFromResultRequest, idempotency_key: IdempotencyKey
    ):
        raise not_implemented()

    app.include_router(router)
