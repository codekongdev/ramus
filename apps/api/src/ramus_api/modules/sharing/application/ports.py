from typing import Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.conversations.public import ConversationRecord
from ramus_api.modules.results.public import ApprovedConclusion, ResultRecord, Revision
from ramus_api.modules.sharing.domain.models import ResultUsage
from ramus_api.modules.sharing.domain.records import PinnedInput, ShareOutcome

TransactionT = TypeVar("TransactionT", contravariant=True)


class ResultUsageQuery(Protocol[TransactionT]):
    def list_usages(self, session: TransactionT, project_id: UUID) -> tuple[ResultUsage, ...]: ...


class SharingRepository(Protocol[TransactionT]):
    """The caller holds the source result lock for the complete send transaction."""

    def pin(
        self, session: TransactionT, conversation_id: UUID, revision: Revision | ApprovedConclusion, actor_id: UUID,
    ) -> ShareOutcome: ...
    def list_inputs(self, session: TransactionT, conversation_id: UUID) -> tuple[PinnedInput, ...]: ...


class ResultReader(Protocol[TransactionT]):
    def get(self, session: TransactionT, result_id: UUID, *, lock: bool = False) -> ResultRecord | None: ...
    def revision(self, session: TransactionT, revision_id: UUID) -> Revision | None: ...
    def latest_versions(self, session: TransactionT, result_ids: tuple[UUID, ...]) -> dict[UUID, int]: ...


class ConversationReader(Protocol[TransactionT]):
    def get_conversation(self, session: TransactionT, conversation_id: UUID) -> ConversationRecord | None: ...
