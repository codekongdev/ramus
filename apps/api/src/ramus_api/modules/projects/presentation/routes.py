"""Project endpoints: list, create, search, and the relationship graph. Stubs until the projects task."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, FastAPI, Query

from ramus_api.container import AppContainer
from ramus_api.modules.projects.presentation.dto import (
    CreateProjectRequest,
    Project,
    ProjectGraph,
    ProjectList,
)
from ramus_api.shared.presentation.error_messages import not_implemented
from ramus_api.shared.presentation.idempotency import IdempotencyKey

SearchQuery = Annotated[str, Query(max_length=100, description="Search text; empty lists everything.")]


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["projects"])

    @router.get("/projects", response_model=ProjectList, operation_id="listProjects")
    def list_projects():
        raise not_implemented()

    @router.post("/projects", response_model=Project, operation_id="createProject")
    def create_project(body: CreateProjectRequest, idempotency_key: IdempotencyKey):
        raise not_implemented()

    @router.get("/projects/search", response_model=ProjectList, operation_id="searchProjects")
    def search_projects(q: SearchQuery = ""):
        raise not_implemented()

    @router.get("/projects/{project_id}/graph", response_model=ProjectGraph, operation_id="getProjectGraph")
    def get_project_graph(project_id: UUID):
        raise not_implemented()

    app.include_router(router)
