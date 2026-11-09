"""Public lookup of a task's result, including a result whose draft is still being prepared."""

from typing import Protocol, TypeVar
from uuid import UUID

TransactionT = TypeVar("TransactionT", contravariant=True)


class TaskResultQuery(Protocol[TransactionT]):
    def for_task(self, session: TransactionT, task_id: UUID) -> UUID | None: ...
