"""Public bounded history reader for result summaries."""

from typing import Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.execution.domain.work import WorkMessage

TransactionT = TypeVar("TransactionT", contravariant=True)


class SummaryInputReader(Protocol[TransactionT]):
    def bounds(self, session: TransactionT, conversation_id: UUID) -> tuple[int, int] | None: ...

    def read(
        self, session: TransactionT, conversation_id: UUID, after_seq: int, through_seq: int
    ) -> tuple[WorkMessage, ...]: ...
