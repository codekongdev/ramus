"""Authenticated conclusion sharing, pinned input reads, and result-based follow-up conversations."""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy.orm import Session

from ramus_api.container import AppContainer
from ramus_api.modules.access.public import AuthenticatedAccount, MembershipReader, require_account
from ramus_api.modules.conversations.composition import CommittedEvents
from ramus_api.modules.conversations.presentation.dto import Conversation
from ramus_api.modules.conversations.public import ConversationReader, SqlFollowupConversations
from ramus_api.modules.results.public import ResultReader, SqlApprovedConclusionReader
from ramus_api.modules.sharing.application.followups import FollowupService
from ramus_api.modules.sharing.application.service import SharingService
from ramus_api.modules.sharing.infrastructure.inputs import SqlConversationInputs
from ramus_api.modules.sharing.infrastructure.repository import SqlSharingRepository
from ramus_api.modules.sharing.presentation.dto import (
    ConversationInputDetail,
    ConversationInputList,
    CreateConversationFromResultRequest,
    ShareOutcomeList,
    ShareResultRevisionRequest,
)
from ramus_api.shared.presentation.idempotency import IdempotencyKey


def register(
    app: FastAPI, container: AppContainer, *, memberships: MembershipReader[Session],
) -> None:
    router = APIRouter(prefix="/api", tags=["sharing"])
    CurrentAccount = Annotated[AuthenticatedAccount, Depends(require_account(container))]
    sharing = SharingService(
        SqlSharingRepository(), ResultReader(), ConversationReader(), container.project_access,
        CommittedEvents(container), memberships, SqlConversationInputs(),
    )
    followups = FollowupService(
        container.database.transaction, memberships, SqlFollowupConversations(),
        SqlApprovedConclusionReader(), SqlConversationInputs(), container.idempotency, CommittedEvents(container),
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
            sharing.require_send_access(session, account.account_id, result_revision_id, targets)
        return container.idempotency.execute_once(
            str(account.account_id), f"sharing.send:{result_revision_id}", idempotency_key,
            body.model_dump(mode="json"),
            lambda session: ShareOutcomeList(items=[asdict(item) for item in sharing.send(
                session, account.account_id, result_revision_id, targets,
            )]).model_dump(mode="json"),
        )

    @router.get(
        "/conversations/{conversation_id}/inputs",
        response_model=ConversationInputList,
        operation_id="listConversationInputs",
    )
    def list_conversation_inputs(conversation_id: UUID, account: CurrentAccount):
        return followups.list_inputs(conversation_id, account.account_id)

    @router.get(
        "/conversations/{conversation_id}/inputs/{input_id}",
        response_model=ConversationInputDetail,
        operation_id="getConversationInput",
    )
    def get_conversation_input(conversation_id: UUID, input_id: UUID, account: CurrentAccount):
        return followups.input_detail(conversation_id, input_id, account.account_id)

    @router.post(
        "/projects/{project_id}/conversations/from-result",
        response_model=Conversation,
        operation_id="createConversationFromResult",
    )
    def create_conversation_from_result(
        project_id: UUID, body: CreateConversationFromResultRequest, idempotency_key: IdempotencyKey,
        account: CurrentAccount,
    ):
        return followups.create(project_id, account.account_id, body.result_revision_id, body.title, idempotency_key)

    app.include_router(router)
