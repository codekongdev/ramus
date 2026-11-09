"""Base classes and small shapes shared by every module's DTOs."""

from pydantic import BaseModel, ConfigDict


class ApiResponse(BaseModel):
    """Base for response DTOs. Immutable once built."""

    model_config = ConfigDict(frozen=True)


class ApiRequest(BaseModel):
    """Base for request DTOs. Unknown fields are rejected at the boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class EmptyRequest(ApiRequest):
    """The empty JSON object body of change requests that carry no data (logout, cancel, retry, summaries)."""


class EmptyResponse(ApiResponse):
    """The empty JSON object body of change responses that have nothing to return."""


class ErrorSummary(ApiResponse):
    """A failure recorded on a run, task, or result draft: a code and the sentence for it."""

    code: str
    message: str
