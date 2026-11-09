"""Resource DTOs: shared skills and materials with versions (docs/contracts.md sections 2 and 3.2)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from ramus_api.shared.presentation.schemas import ApiRequest, ApiResponse

MAX_RESOURCE_TEXT_LENGTH = 100_000

ResourceKind = Literal["skill", "text", "file"]


class ResourceLatest(ApiResponse):
    revision_id: UUID
    number: int
    name: str
    description: str


class AppliedRevisionRef(ApiResponse):
    revision_id: UUID
    number: int


class ResourceSummary(ApiResponse):
    id: UUID
    kind: ResourceKind
    latest: ResourceLatest
    applied: AppliedRevisionRef | None


class ResourceSummaryList(ApiResponse):
    items: list[ResourceSummary]


class ResourceRevision(ApiResponse):
    id: UUID
    resource_id: UUID
    number: int
    name: str
    description: str
    instructions: str | None
    content: str | None
    file_name: str | None
    created_by: UUID
    created_at: datetime


class ResourceRevisionEntry(ApiResponse):
    id: UUID
    number: int
    name: str
    created_by: UUID
    created_at: datetime


class ResourceDetail(ApiResponse):
    id: UUID
    kind: ResourceKind
    latest_revision_id: UUID
    revisions: list[ResourceRevisionEntry]
    revision: ResourceRevision


class AppliedResource(ApiResponse):
    resource_id: UUID
    revision_id: UUID
    number: int
    name: str
    kind: ResourceKind


class AppliedResourceList(ApiResponse):
    items: list[AppliedResource]


class CreateResourceRequest(ApiRequest):
    kind: ResourceKind
    name: str = Field(min_length=1)
    description: str
    instructions: str | None = Field(default=None, max_length=MAX_RESOURCE_TEXT_LENGTH)
    content: str | None = Field(default=None, max_length=MAX_RESOURCE_TEXT_LENGTH)
    file_name: str | None = None


class CreateResourceRevisionRequest(ApiRequest):
    base_revision_id: UUID
    name: str = Field(min_length=1)
    description: str
    instructions: str | None = Field(default=None, max_length=MAX_RESOURCE_TEXT_LENGTH)
    content: str | None = Field(default=None, max_length=MAX_RESOURCE_TEXT_LENGTH)
    file_name: str | None = None


class CreateResourceRevisionResponse(ApiResponse):
    revision: ResourceRevision
    created: bool


class ReplaceAppliedResourcesRequest(ApiRequest):
    revision_ids: list[UUID]
