"""Authenticated project creation and reads; the relationship graph remains an A9 stub."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from ramus_api.container import AppContainer
from ramus_api.modules.access.presentation.dto import Account
from ramus_api.modules.access.public import (
    AuthenticatedAccount,
    MembershipReader,
    MembershipWriter,
    require_account,
)
from ramus_api.modules.projects.application.create import CreateProject
from ramus_api.modules.projects.application.queries import ProjectNotFound, ProjectQueries
from ramus_api.modules.projects.infrastructure.queries import SqlProjectRepository
from ramus_api.modules.projects.presentation.dto import (
    CreateProjectRequest,
    Project,
    ProjectGraph,
    ProjectList,
    ProjectParticipants,
)
from ramus_api.shared.presentation.error_messages import not_implemented
from ramus_api.shared.presentation.idempotency import IdempotencyKey

SearchQuery = Annotated[str, Query(max_length=100, description="Search text; empty lists everything.")]


def register(
    app: FastAPI, container: AppContainer, *, memberships: MembershipReader[Session],
    membership_writer: MembershipWriter[Session],
) -> None:
    router = APIRouter(prefix="/api", tags=["projects"])
    repository = SqlProjectRepository()
    queries = ProjectQueries(container.database.transaction, memberships, repository)
    creator = CreateProject(container.idempotency, repository, membership_writer)
    CurrentAccount = Annotated[AuthenticatedAccount, Depends(require_account(container))]

    @router.get("/projects", response_model=ProjectList, operation_id="listProjects")
    def list_projects(account: CurrentAccount):
        return ProjectList(
            items=[
                Project(id=project.id, name=project.name, is_shared_sample=project.is_shared_sample)
                for project in queries.list_projects(account.account_id)
            ]
        )

    @router.get(
        "/projects/{project_id}/participants",
        response_model=ProjectParticipants,
        operation_id="listProjectParticipants",
    )
    def list_participants(project_id: UUID, account: CurrentAccount):
        try:
            people = queries.participants(account.account_id, project_id)
        except ProjectNotFound:
            raise HTTPException(status_code=404) from None
        return ProjectParticipants(
            items=[
                Account(id=person.id, email=person.email, display_name=person.display_name)
                for person in people
            ]
        )

    @router.post("/projects", response_model=Project, operation_id="createProject")
    def create_project(
        body: CreateProjectRequest, idempotency_key: IdempotencyKey, account: CurrentAccount,
    ):
        return creator.execute(account.account_id, body.name, idempotency_key)

    @router.get("/projects/search", response_model=ProjectList, operation_id="searchProjects")
    def search_projects(account: CurrentAccount, q: SearchQuery = ""):
        return ProjectList(
            items=[
                Project(id=project.id, name=project.name, is_shared_sample=project.is_shared_sample)
                for project in queries.list_projects(account.account_id, q)
            ]
        )

    @router.get("/projects/{project_id}/graph", response_model=ProjectGraph, operation_id="getProjectGraph")
    def get_project_graph(project_id: UUID):
        raise not_implemented()

    app.include_router(router)
