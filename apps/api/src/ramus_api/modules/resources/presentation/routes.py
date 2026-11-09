"""Resource endpoints: shared skills/materials, versions, and what a conversation applies.

B1: list/create resources and get/replace the versions a conversation pins.
B2: resource detail/history and saving a new revision.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlalchemy.orm import Session

from ramus_api.container import AppContainer
from ramus_api.modules.access.presentation.current_account import AuthenticatedAccount, require_account
from ramus_api.modules.conversations.composition import CommittedEvents
from ramus_api.modules.resources.application.use_cases import (
    Outcome,
    ResourceDraft,
    ResourceUseCases,
    RevisionDraft,
)
from ramus_api.modules.resources.domain.models import ResourceKind
from ramus_api.modules.resources.domain.rules import ResourceRuleError
from ramus_api.modules.resources.infrastructure.lookups import (
    MembershipFromProjectAccess,
    SqlConversationDirectory,
)
from ramus_api.modules.resources.infrastructure.repository import SqlResourceRepository
from ramus_api.modules.resources.presentation.dto import (
    AppliedResourceList,
    CreateResourceRequest,
    CreateResourceRevisionRequest,
    CreateResourceRevisionResponse,
    ReplaceAppliedResourcesRequest,
    ResourceDetail,
    ResourceSummaryList,
)
from ramus_api.modules.resources.presentation.mapping import (
    applied_list,
    resource_detail,
    revision_dto,
    summary_list,
    to_business_error,
)
from ramus_api.shared.domain.primitives import new_id, utc_now
from ramus_api.shared.presentation.idempotency import IdempotencyKey

SearchQuery = Annotated[str, Query(max_length=100, description="Matches name and description.")]
AppliedIn = Annotated[
    UUID | None, Query(description="Fill `applied` with the versions this conversation uses.")
]


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["resources"])
    CurrentAccount = Annotated[AuthenticatedAccount, Depends(require_account(container))]
    use_cases: ResourceUseCases[Session] = ResourceUseCases(
        repository=SqlResourceRepository(),
        membership=MembershipFromProjectAccess(container.project_access),
        conversations=SqlConversationDirectory(),
        new_id=new_id,
        now=utc_now,
    )
    events = CommittedEvents(container)

    def read(work: Callable[[Session], Any]) -> Any:
        try:
            with container.database.transaction() as session:
                return work(session)
        except ResourceRuleError as error:
            raise to_business_error(error) from None

    def change(
        account: AuthenticatedAccount,
        scope: str,
        key: str,
        payload: dict[str, Any],
        work: Callable[[Session], Outcome[Any]],
        render: Callable[[Any], Any],
    ) -> dict[str, Any]:
        def operation(session: Session) -> dict[str, Any]:
            outcome = work(session)
            for event in outcome.events:
                events.after_commit(session, event)
            return render(outcome.value).model_dump(mode="json")

        try:
            return container.idempotency.execute_once(str(account.account_id), scope, key, payload, operation)
        except ResourceRuleError as error:
            raise to_business_error(error) from None

    @router.get(
        "/projects/{project_id}/resources",
        response_model=ResourceSummaryList,
        operation_id="listResources",
    )
    def list_resources(
        project_id: UUID, account: CurrentAccount, q: SearchQuery = "", conversation_id: AppliedIn = None
    ):
        return summary_list(
            read(lambda s: use_cases.search(s, account.account_id, project_id, q, conversation_id))
        )

    @router.post(
        "/projects/{project_id}/resources",
        response_model=ResourceDetail,
        operation_id="createResource",
    )
    def create_resource(
        project_id: UUID,
        body: CreateResourceRequest,
        idempotency_key: IdempotencyKey,
        account: CurrentAccount,
    ):
        draft = ResourceDraft(
            ResourceKind(body.kind),
            body.name,
            body.description,
            body.instructions,
            body.content,
            body.file_name,
        )
        return change(
            account,
            f"resources.create:{project_id}",
            idempotency_key,
            body.model_dump(mode="json"),
            lambda s: use_cases.create(s, account.account_id, project_id, draft),
            resource_detail,
        )

    @router.get("/resources/{resource_id}", response_model=ResourceDetail, operation_id="getResource")
    def get_resource(resource_id: UUID, account: CurrentAccount, revision_id: UUID | None = None):
        history, selected = read(lambda s: use_cases.detail(s, account.account_id, resource_id, revision_id))
        return resource_detail(history, selected)

    @router.post(
        "/resources/{resource_id}/revisions",
        response_model=CreateResourceRevisionResponse,
        operation_id="createResourceRevision",
    )
    def create_resource_revision(
        resource_id: UUID,
        body: CreateResourceRevisionRequest,
        idempotency_key: IdempotencyKey,
        account: CurrentAccount,
    ):
        draft = RevisionDraft(
            body.base_revision_id,
            body.name,
            body.description,
            body.instructions,
            body.content,
            body.file_name,
        )
        return change(
            account,
            f"resources.revision:{resource_id}",
            idempotency_key,
            body.model_dump(mode="json"),
            lambda s: use_cases.save_revision(s, account.account_id, resource_id, draft),
            lambda saved: CreateResourceRevisionResponse(
                revision=revision_dto(saved.revision), created=saved.created
            ),
        )

    @router.get(
        "/conversations/{conversation_id}/resources",
        response_model=AppliedResourceList,
        operation_id="listAppliedResources",
    )
    def list_applied_resources(conversation_id: UUID, account: CurrentAccount):
        return applied_list(read(lambda s: use_cases.list_applied(s, account.account_id, conversation_id)))

    @router.put(
        "/conversations/{conversation_id}/resources",
        response_model=AppliedResourceList,
        operation_id="replaceAppliedResources",
    )
    def replace_applied_resources(
        conversation_id: UUID,
        body: ReplaceAppliedResourcesRequest,
        idempotency_key: IdempotencyKey,
        account: CurrentAccount,
    ):
        return change(
            account,
            f"resources.applied:{conversation_id}",
            idempotency_key,
            body.model_dump(mode="json"),
            lambda s: use_cases.replace_applied(s, account.account_id, conversation_id, body.revision_ids),
            applied_list,
        )

    app.include_router(router)
