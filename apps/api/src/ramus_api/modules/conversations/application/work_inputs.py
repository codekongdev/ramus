"""Public read boundary used by execution; implementations belong to conversations."""

from typing import Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.execution.domain.work import WorkHistory

TransactionT = TypeVar("TransactionT", contravariant=True)


class WorkInputReader(Protocol[TransactionT]):
    def read(self, session: TransactionT, conversation_id: UUID, run_id: UUID) -> WorkHistory:
        """Returns history ending at this run's original human request or branch start input."""

    def lock_parent(self, session: TransactionT, conversation_id: UUID) -> None:
        """Keeps the parent conversation stable until the branch transaction ends."""
