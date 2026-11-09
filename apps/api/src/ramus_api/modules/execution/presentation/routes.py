"""Execution endpoints: the task queue of a conversation, and cancel/retry. Stubs until the executor lands."""

from uuid import UUID

from fastapi import APIRouter, FastAPI

from ramus_api.container import AppContainer
from ramus_api.modules.execution.presentation.dto import Task, TaskList
from ramus_api.shared.presentation.error_messages import not_implemented
from ramus_api.shared.presentation.idempotency import IdempotencyKey
from ramus_api.shared.presentation.schemas import EmptyRequest


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["execution"])

    @router.get(
        "/conversations/{conversation_id}/tasks",
        response_model=TaskList,
        operation_id="listConversationTasks",
    )
    def list_conversation_tasks(conversation_id: UUID):
        raise not_implemented()

    @router.get("/tasks/{task_id}", response_model=Task, operation_id="getTask")
    def get_task(task_id: UUID):
        raise not_implemented()

    @router.post("/tasks/{task_id}/cancel", response_model=Task, operation_id="cancelTask")
    def cancel_task(task_id: UUID, body: EmptyRequest, idempotency_key: IdempotencyKey):
        raise not_implemented()

    @router.post("/tasks/{task_id}/retry", response_model=Task, operation_id="retryTask")
    def retry_task(task_id: UUID, body: EmptyRequest, idempotency_key: IdempotencyKey):
        raise not_implemented()

    app.include_router(router)
