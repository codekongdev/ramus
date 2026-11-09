"""Authenticated result summaries, approvals, and the project's saved result list."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI

from ramus_api.container import AppContainer
from ramus_api.modules.access.presentation.current_account import AuthenticatedAccount, require_account
from ramus_api.modules.conversations.composition import CommittedEvents
from ramus_api.modules.conversations.infrastructure.repository import SqlConversationRepository
from ramus_api.modules.conversations.infrastructure.summary_inputs import SqlSummaryInputReader
from ramus_api.modules.execution.infrastructure.summary_tasks import SqlSummaryTaskReader
from ramus_api.modules.resources.infrastructure.context_provider import build_context_provider
from ramus_api.modules.results.application.service import ResultService
from ramus_api.modules.results.infrastructure.repository import SqlResultRepository
from ramus_api.modules.results.presentation.dto import (
    ProjectResultList,
    Result,
    ResultRevision,
    SaveResultRevisionRequest,
)
from ramus_api.modules.results.presentation.mapping import project_result_dto, result_dto, revision_dto
from ramus_api.shared.presentation.idempotency import IdempotencyKey
from ramus_api.shared.presentation.schemas import EmptyRequest


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["results"])
    CurrentAccount = Annotated[AuthenticatedAccount, Depends(require_account(container))]
    service = ResultService(
        SqlResultRepository(), SqlSummaryTaskReader(), SqlConversationRepository(), SqlSummaryInputReader(),
        build_context_provider(), container.project_access, container.run_requester, container.run_reader,
        CommittedEvents(container),
    )

    @router.post("/tasks/{task_id}/summaries", response_model=Result, operation_id="createTaskSummary")
    def create_task_summary(task_id: UUID, body: EmptyRequest, idempotency_key: IdempotencyKey, account: CurrentAccount):
        # Stored responses must not grant access after project membership is revoked.
        with container.database.transaction() as session:
            service.require_task_access(session, account.account_id, task_id)
        return container.idempotency.execute_once(
            str(account.account_id), f"results.summary:{task_id}", idempotency_key, {},
            lambda session: result_dto(service.summarize(session, account.account_id, task_id)).model_dump(mode="json"),
        )

    @router.get("/results/{result_id}", response_model=Result, operation_id="getResult")
    def get_result(result_id: UUID, account: CurrentAccount):
        with container.database.transaction() as session:
            return result_dto(service.get(session, account.account_id, result_id))

    @router.get("/result-revisions/{result_revision_id}", response_model=ResultRevision, operation_id="getResultRevision")
    def get_result_revision(result_revision_id: UUID, account: CurrentAccount):
        with container.database.transaction() as session:
            return revision_dto(service.revision(session, account.account_id, result_revision_id))

    @router.post("/results/{result_id}/revisions", response_model=ResultRevision, operation_id="saveResultRevision")
    def save_result_revision(
        result_id: UUID, body: SaveResultRevisionRequest, idempotency_key: IdempotencyKey, account: CurrentAccount,
    ):
        with container.database.transaction() as session:
            service.get(session, account.account_id, result_id)
        return container.idempotency.execute_once(
            str(account.account_id), f"results.revision:{result_id}", idempotency_key, body.model_dump(mode="json"),
            lambda session: revision_dto(service.save(
                session, account.account_id, result_id, body.base_version, body.conclusion, body.source_run_id,
            )).model_dump(mode="json"),
        )

    @router.get("/projects/{project_id}/results", response_model=ProjectResultList, operation_id="listProjectResults")
    def list_project_results(project_id: UUID, account: CurrentAccount):
        with container.database.transaction() as session:
            return ProjectResultList(items=[
                project_result_dto(result)
                for result in service.list_project(session, account.account_id, project_id)
            ])

    app.include_router(router)
