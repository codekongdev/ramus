"""Run lifecycle rules as pure functions over immutable run state."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from ramus_api.modules.execution.domain import errors as codes
from ramus_api.modules.execution.domain.models import (
    LlmFailure,
    LlmRequest,
    RunInputSnapshot,
    RunPurpose,
    RunStatus,
    RunView,
)

ACTIVE_STATUSES = frozenset({RunStatus.PENDING, RunStatus.RUNNING})
RETRYABLE_STATUSES = frozenset({RunStatus.FAILED, RunStatus.CANCELLED})


@dataclass(frozen=True)
class RunFailure:
    """What is stored for a failed run: a code, safe parameters, and whether a retry can help."""

    code: str
    retryable: bool = True
    params: Mapping[str, Any] | None = None


INTERRUPTED = RunFailure(codes.RUN_INTERRUPTED)
TIMED_OUT = RunFailure(codes.RUN_TIMED_OUT)


@dataclass(frozen=True)
class RunState:
    """A stored run row. ``view`` is the public subset handed to purpose handlers."""

    id: UUID
    project_id: UUID
    conversation_id: UUID
    task_id: UUID | None
    purpose: RunPurpose
    target_id: UUID | None
    status: RunStatus
    requested_by: UUID
    credential_account_id: UUID
    input_snapshot: RunInputSnapshot
    attempt: int
    error_code: str | None
    error_params: Mapping[str, Any] | None
    heartbeat_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "purpose", RunPurpose(self.purpose))
        object.__setattr__(self, "status", RunStatus(self.status))

    @property
    def view(self) -> RunView:
        return RunView(
            id=self.id,
            project_id=self.project_id,
            conversation_id=self.conversation_id,
            task_id=self.task_id,
            purpose=self.purpose,
            target_id=self.target_id,
            status=self.status,
            requested_by=self.requested_by,
            credential_account_id=self.credential_account_id,
            input_snapshot=self.input_snapshot,
        )


def cancel_denial(state: RunState, actor_id: UUID) -> str | None:
    """Error code that forbids ``actor_id`` from cancelling, or ``None`` when allowed (contract C7)."""
    if state.requested_by != actor_id:
        return codes.FORBIDDEN
    if state.status not in ACTIVE_STATUSES:
        return codes.RUN_NOT_CANCELLABLE
    return None


def retry_denial(state: RunState, actor_id: UUID) -> str | None:
    """Error code that forbids ``actor_id`` from retrying, or ``None`` when allowed (contract C7)."""
    if state.requested_by != actor_id:
        return codes.FORBIDDEN
    if state.status not in RETRYABLE_STATUSES:
        return codes.RUN_NOT_RETRYABLE
    return None


def failure_from_exception(error: BaseException) -> RunFailure:
    """Keeps only a code. Exception text may hold provider payloads or keys and is never copied."""
    if isinstance(error, LlmFailure):
        return RunFailure(error.code, retryable=error.retryable)
    if isinstance(error, TimeoutError):
        return RunFailure(codes.LLM_TIMEOUT)
    return RunFailure(codes.LLM_UNAVAILABLE)


def credential_failure(run: RunView, request: LlmRequest) -> RunFailure | None:
    """A model request may only spend the requester's own key (ON-AC-08)."""
    if request.credential_account_id != run.credential_account_id:
        return RunFailure(codes.RUN_CREDENTIAL_MISMATCH, retryable=False)
    return None
