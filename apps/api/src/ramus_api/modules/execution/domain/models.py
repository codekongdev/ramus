"""Framework-free execution values shared by both feature tracks."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal
from uuid import UUID


class RunPurpose(StrEnum):
    WORK = "work"
    SUMMARY = "summary"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ResourceInput:
    resource_id: UUID
    revision_id: UUID
    kind: Literal["skill", "text", "file"]
    name: str
    instructions: str | None
    content: str | None


@dataclass(frozen=True)
class ResultInput:
    result_id: UUID
    result_revision_id: UUID
    version: int
    title: str
    conclusion: str


@dataclass(frozen=True)
class ConversationContext:
    resources: tuple[ResourceInput, ...] = ()
    results: tuple[ResultInput, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "resources", tuple(self.resources))
        object.__setattr__(self, "results", tuple(self.results))
        if len({item.resource_id for item in self.resources}) != len(self.resources):
            raise ValueError("A context can pin only one revision per resource")
        if len({item.result_id for item in self.results}) != len(self.results):
            raise ValueError("A context can pin only one revision per result")


@dataclass(frozen=True)
class RunRequest:
    project_id: UUID
    conversation_id: UUID
    task_id: UUID | None
    purpose: RunPurpose
    target_id: UUID | None
    requested_by: UUID

    def __post_init__(self) -> None:
        object.__setattr__(self, "purpose", RunPurpose(self.purpose))
        if (self.purpose == RunPurpose.SUMMARY) != (self.target_id is not None):
            raise ValueError("Only summary runs require a result target_id")


@dataclass(frozen=True)
class RunRef:
    run_id: UUID
    status: RunStatus


@dataclass(frozen=True)
class RunInputSnapshot:
    message_from_seq: int | None = None
    message_to_seq: int | None = None
    resource_revision_ids: tuple[UUID, ...] = ()
    input_result_revision_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_revision_ids", tuple(self.resource_revision_ids))
        object.__setattr__(self, "input_result_revision_ids", tuple(self.input_result_revision_ids))
        start, end = self.message_from_seq, self.message_to_seq
        if (start is None) != (end is None) or (start is not None and (start < 1 or end < start)):
            raise ValueError("Message range must be empty or a positive inclusive range")


@dataclass(frozen=True)
class RunView:
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


@dataclass(frozen=True)
class RunError:
    """Safe application error; provider exceptions/raw payloads must not be copied here."""

    code: str
    message: str
    retryable: bool = True


@dataclass(frozen=True)
class LlmMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class LlmRequest:
    purpose: RunPurpose
    messages: tuple[LlmMessage, ...]
    credential_account_id: UUID
    context: ConversationContext = field(default_factory=ConversationContext)
    is_child: bool = False
    message_from_seq: int | None = None
    message_to_seq: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "purpose", RunPurpose(self.purpose))
        object.__setattr__(self, "messages", tuple(self.messages))
        RunInputSnapshot(self.message_from_seq, self.message_to_seq)


class LlmFailure(Exception):
    """A sanitized gateway failure; never retain credentials or untrusted model text."""

    def __init__(self, code: str = "LLM_UNAVAILABLE", *, retryable: bool = True) -> None:
        super().__init__("AI 요청을 처리하지 못했습니다. 다시 시도해 주세요.")
        self.code = code
        self.retryable = retryable
