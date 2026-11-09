"""Resource endpoints: shared skills/materials, versions, and what a conversation applies. Stubs for now."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, FastAPI, Query

from ramus_api.container import AppContainer
from ramus_api.modules.resources.presentation.dto import (
    AppliedResourceList,
    CreateResourceRequest,
    CreateResourceRevisionRequest,
    CreateResourceRevisionResponse,
    ReplaceAppliedResourcesRequest,
    ResourceDetail,
    ResourceSummaryList,
)
from ramus_api.shared.presentation.error_messages import not_implemented
from ramus_api.shared.presentation.idempotency import IdempotencyKey

SearchQuery = Annotated[str, Query(max_length=100, description="Matches name and description.")]
AppliedIn = Annotated[
    UUID | None, Query(description="Fill `applied` with the versions this conversation uses.")
]


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["resources"])

    @router.get(
        "/projects/{project_id}/resources",
        response_model=ResourceSummaryList,
        operation_id="listResources",
    )
    def list_resources(project_id: UUID, q: SearchQuery = "", conversation_id: AppliedIn = None):
        raise not_implemented()

    @router.post(
        "/projects/{project_id}/resources",
        response_model=ResourceDetail,
        operation_id="createResource",
    )
    def create_resource(project_id: UUID, body: CreateResourceRequest, idempotency_key: IdempotencyKey):
        raise not_implemented()

    @router.get("/resources/{resource_id}", response_model=ResourceDetail, operation_id="getResource")
    def get_resource(resource_id: UUID, revision_id: UUID | None = None):
        raise not_implemented()

    @router.post(
        "/resources/{resource_id}/revisions",
        response_model=CreateResourceRevisionResponse,
        operation_id="createResourceRevision",
    )
    def create_resource_revision(
        resource_id: UUID, body: CreateResourceRevisionRequest, idempotency_key: IdempotencyKey
    ):
        raise not_implemented()

    @router.get(
        "/conversations/{conversation_id}/resources",
        response_model=AppliedResourceList,
        operation_id="listAppliedResources",
    )
    def list_applied_resources(conversation_id: UUID):
        raise not_implemented()

    @router.put(
        "/conversations/{conversation_id}/resources",
        response_model=AppliedResourceList,
        operation_id="replaceAppliedResources",
    )
    def replace_applied_resources(
        conversation_id: UUID, body: ReplaceAppliedResourcesRequest, idempotency_key: IdempotencyKey
    ):
        raise not_implemented()

    app.include_router(router)
