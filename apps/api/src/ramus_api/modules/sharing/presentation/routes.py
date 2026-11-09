"""Authenticated conclusion sharing; new-conversation creation is the B7 extension point."""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI

from ramus_api.container import AppContainer
from ramus_api.modules.access.presentation.current_account import AuthenticatedAccount, require_account
from ramus_api.modules.conversations.composition import CommittedEvents
from ramus_api.modules.conversations.presentation.dto import Conversation
from ramus_api.modules.conversations.public import ConversationReader
from ramus_api.modules.results.public import ResultReader
from ramus_api.modules.sharing.application.service import SharingService
from ramus_api.modules.sharing.infrastructure.repository import SqlSharingRepository
from ramus_api.modules.sharing.presentation.dto import (
    ConversationInputDetail,
    ConversationInputList,
    CreateConversationFromResultRequest,
    ShareOutcomeList,
    ShareResultRevisionRequest,
)
from ramus_api.shared.presentation.error_messages import not_implemented
from ramus_api.shared.presentation.idempotency import IdempotencyKey


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["sharing"])
    CurrentAccount = Annotated[AuthenticatedAccount, Depends(require_account(container))]
    service = SharingService(
        SqlSharingRepository(), ResultReader(), ConversationReader(), container.project_access,
        CommittedEvents(container),
    )

    @router.post(
        "/result-revisions/{result_revision_id}/shares",
        response_model=ShareOutcomeList,
        operation_id="shareResultRevision",
    )
    def share_result_revision(
        result_revision_id: UUID, body: ShareResultRevisionRequest, idempotency_key: IdempotencyKey,
        account: CurrentAccount,
    ):
        targets = tuple(body.conversation_ids)
        # A receipt must not grant access after source or target membership is revoked.
        with container.database.transaction() as session:
            service.require_send_access(session, account.account_id, result_revision_id, targets)
        return container.idempotency.execute_once(
            str(account.account_id), f"sharing.send:{result_revision_id}", idempotency_key,
            body.model_dump(mode="json"),
            lambda session: ShareOutcomeList(items=[asdict(item) for item in service.send(
                session, account.account_id, result_revision_id, targets,
            )]).model_dump(mode="json"),
        )

    @router.get(
        "/conversations/{conversation_id}/inputs",
        response_model=ConversationInputList,
        operation_id="listConversationInputs",
    )
    def list_conversation_inputs(conversation_id: UUID, account: CurrentAccount):
        with container.database.transaction() as session:
            return ConversationInputList(items=[
                {**asdict(item.pinned), "latest_version": item.latest_version}
                for item in service.received(session, account.account_id, conversation_id)
            ])

    @router.get(
        "/conversations/{conversation_id}/inputs/{input_id}",
        response_model=ConversationInputDetail,
        operation_id="getConversationInput",
    )
    def get_conversation_input(conversation_id: UUID, input_id: UUID):
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
