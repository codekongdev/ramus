"""Public read boundary for results; callers never update execution-owned task rows."""

from dataclasses import dataclass
from typing import Protocol, TypeVar
from uuid import UUID

TransactionT = TypeVar("TransactionT", contravariant=True)


@dataclass(frozen=True)
class SummaryTask:
    id: UUID
    conversation_id: UUID
    title: str
    status: str


class SummaryTaskReader(Protocol[TransactionT]):
    def get(self, session: TransactionT, task_id: UUID, *, lock: bool = False) -> SummaryTask | None: ...
