"""Result endpoints: summarising a task, reading and approving conclusions. Stubs for now."""

from uuid import UUID

from fastapi import APIRouter, FastAPI

from ramus_api.container import AppContainer
from ramus_api.modules.results.presentation.dto import (
    ProjectResultList,
    Result,
    ResultRevision,
    SaveResultRevisionRequest,
)
from ramus_api.shared.presentation.error_messages import not_implemented
from ramus_api.shared.presentation.idempotency import IdempotencyKey
from ramus_api.shared.presentation.schemas import EmptyRequest


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["results"])

    @router.post("/tasks/{task_id}/summaries", response_model=Result, operation_id="createTaskSummary")
    def create_task_summary(task_id: UUID, body: EmptyRequest, idempotency_key: IdempotencyKey):
        raise not_implemented()

    @router.get("/results/{result_id}", response_model=Result, operation_id="getResult")
    def get_result(result_id: UUID):
        raise not_implemented()

    @router.get(
        "/result-revisions/{result_revision_id}",
        response_model=ResultRevision,
        operation_id="getResultRevision",
    )
    def get_result_revision(result_revision_id: UUID):
        raise not_implemented()

    @router.post(
        "/results/{result_id}/revisions",
        response_model=ResultRevision,
        operation_id="saveResultRevision",
    )
    def save_result_revision(
        result_id: UUID, body: SaveResultRevisionRequest, idempotency_key: IdempotencyKey
    ):
        raise not_implemented()

    @router.get(
        "/projects/{project_id}/results",
        response_model=ProjectResultList,
        operation_id="listProjectResults",
    )
    def list_project_results(project_id: UUID):
        raise not_implemented()

    app.include_router(router)
