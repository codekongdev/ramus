"""Project DTOs: projects and the relationship graph (docs/contracts.md sections 2 and 3.1)."""

from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field

from ramus_api.modules.access.presentation.dto import Account
from ramus_api.modules.execution.presentation.dto import TaskStatus
from ramus_api.shared.presentation.schemas import ApiRequest, ApiResponse

MAX_PROJECT_NAME_LENGTH = 100

GraphEdgeKind = Literal["branch", "uses_result"]


class Project(ApiResponse):
    id: UUID
    name: str
    is_shared_sample: bool


class ProjectList(ApiResponse):
    items: list[Project]


class ProjectParticipants(ApiResponse):
    items: list[Account]


class CreateProjectRequest(ApiRequest):
    name: str = Field(min_length=1, max_length=MAX_PROJECT_NAME_LENGTH)


class GraphNode(ApiResponse):
    conversation_id: UUID
    title: str
    parent_id: UUID | None
    task_status: TaskStatus | None


class GraphEdge(ApiResponse):
    """``from`` is a Python keyword, so the attribute is ``source`` and the JSON name is ``from``."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    kind: GraphEdgeKind
    source: UUID = Field(alias="from")
    to: UUID


class ProjectGraph(ApiResponse):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
