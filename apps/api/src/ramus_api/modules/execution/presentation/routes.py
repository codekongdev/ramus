"""Authenticated task queue, details, and idempotent control of the current work run."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI

from ramus_api.container import AppContainer
from ramus_api.modules.access.public import AuthenticatedAccount, require_account
from ramus_api.modules.conversations.infrastructure.repository import SqlConversationRepository
from ramus_api.modules.execution.application.tasks import TaskService
from ramus_api.modules.execution.infrastructure.task_queries import SqlTaskRepository
from ramus_api.modules.execution.presentation.dto import Task, TaskList
from ramus_api.modules.results.infrastructure.task_results import SqlTaskResultQuery
from ramus_api.shared.presentation.idempotency import IdempotencyKey
from ramus_api.shared.presentation.schemas import EmptyRequest


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["execution"])
    CurrentAccount = Annotated[AuthenticatedAccount, Depends(require_account(container))]
    service = TaskService(
        transaction=container.database.transaction,
        tasks=SqlTaskRepository(SqlTaskResultQuery()),
        conversations=SqlConversationRepository(),
        access=container.project_access,
        idempotency=container.idempotency,
        control=container.execution_runtime.control if container.execution_runtime is not None else None,
    )

    @router.get(
        "/conversations/{conversation_id}/tasks",
        response_model=TaskList,
        operation_id="listConversationTasks",
    )
    def list_conversation_tasks(conversation_id: UUID, account: CurrentAccount):
        return service.list_tasks(conversation_id, account.account_id)

    @router.get("/tasks/{task_id}", response_model=Task, operation_id="getTask")
    def get_task(task_id: UUID, account: CurrentAccount):
        return service.get_task(task_id, account.account_id)

    @router.post("/tasks/{task_id}/cancel", response_model=Task, operation_id="cancelTask")
    def cancel_task(task_id: UUID, body: EmptyRequest, idempotency_key: IdempotencyKey, account: CurrentAccount):
        return service.change(task_id, account.account_id, "cancel", idempotency_key)

    @router.post("/tasks/{task_id}/retry", response_model=Task, operation_id="retryTask")
    def retry_task(task_id: UUID, body: EmptyRequest, idempotency_key: IdempotencyKey, account: CurrentAccount):
        return service.change(task_id, account.account_id, "retry", idempotency_key)

    app.include_router(router)
