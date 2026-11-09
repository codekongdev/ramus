"""Execution-owned task persistence and lifecycle projection inside the caller's transaction."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.execution.domain.state import RunState
from ramus_api.modules.realtime.domain.events import ProjectEvent

TransactionT = TypeVar("TransactionT", contravariant=True)


@dataclass(frozen=True)
class NewBranchTask:
    id: UUID
    source_conversation_id: UUID
    child_conversation_id: UUID
    source_run_id: UUID
    ordinal: int
    title: str
    goal: str
    requested_by: UUID


class BranchTaskStore(Protocol[TransactionT]):
    def create(self, session: TransactionT, task: NewBranchTask) -> None: ...

    def goal(self, session: TransactionT, task_id: UUID) -> str: ...


class TaskLifecycle(Protocol[TransactionT]):
    def project(
        self, session: TransactionT, state: RunState, occurred_at: datetime
    ) -> ProjectEvent | None:
        """Projects current work-run status and returns the corresponding task.updated event."""
