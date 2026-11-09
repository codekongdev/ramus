"""Authorized task queries; cancel/retry remain separate execution-control work."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI

from ramus_api.container import AppContainer
from ramus_api.modules.access.presentation.current_account import AuthenticatedAccount, require_account
from ramus_api.modules.conversations.infrastructure.repository import SqlConversationRepository
from ramus_api.modules.execution.application.task_queries import TaskQueries
from ramus_api.modules.execution.infrastructure.task_queries import SqlTaskQueryStore
from ramus_api.modules.execution.presentation.dto import Task, TaskList
from ramus_api.modules.results.infrastructure.task_results import SqlTaskResultQuery
from ramus_api.shared.presentation.error_messages import not_implemented
from ramus_api.shared.presentation.idempotency import IdempotencyKey
from ramus_api.shared.presentation.schemas import EmptyRequest


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["execution"])
    CurrentAccount = Annotated[AuthenticatedAccount, Depends(require_account(container))]
    queries = TaskQueries(
        container.database.transaction, SqlTaskQueryStore(SqlTaskResultQuery()),
        SqlConversationRepository(), container.project_access,
    )

    @router.get(
        "/conversations/{conversation_id}/tasks",
        response_model=TaskList,
        operation_id="listConversationTasks",
    )
    def list_conversation_tasks(conversation_id: UUID, account: CurrentAccount):
        return queries.list(conversation_id, account.account_id)

    @router.get("/tasks/{task_id}", response_model=Task, operation_id="getTask")
    def get_task(task_id: UUID, account: CurrentAccount):
        return queries.get(task_id, account.account_id)

    @router.post("/tasks/{task_id}/cancel", response_model=Task, operation_id="cancelTask")
    def cancel_task(task_id: UUID, body: EmptyRequest, idempotency_key: IdempotencyKey):
        raise not_implemented()

    @router.post("/tasks/{task_id}/retry", response_model=Task, operation_id="retryTask")
    def retry_task(task_id: UUID, body: EmptyRequest, idempotency_key: IdempotencyKey):
        raise not_implemented()

    app.include_router(router)
