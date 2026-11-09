from typing import Any, Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.conversations.domain.models import AuthorKind, NewChildConversation, NewMessage
from ramus_api.modules.conversations.domain.views import ConversationRecord, MessageRecord
from ramus_api.modules.realtime.domain.events import ProjectEvent

TransactionT = TypeVar("TransactionT", contravariant=True)


class ConversationWriter(Protocol[TransactionT]):
    """Writes into the caller's transaction; execution never accesses conversation tables."""

    def append_message(self, session: TransactionT, message: NewMessage) -> UUID: ...

    def create_child(self, session: TransactionT, conversation: NewChildConversation) -> UUID: ...


class ProjectAccess(Protocol[TransactionT]):
    def require_member(self, session: TransactionT, project_id: UUID, account_id: UUID) -> None: ...

    def display_names(self, session: TransactionT, account_ids: set[UUID]) -> dict[UUID, str]: ...


class RunReader(Protocol[TransactionT]):
    def active_run(self, session: TransactionT, conversation_id: UUID) -> dict[str, Any] | None: ...

    def get_run(self, session: TransactionT, run_id: UUID) -> dict[str, Any]: ...


class CommittedEvents(Protocol[TransactionT]):
    def after_commit(self, session: TransactionT, event: ProjectEvent) -> None: ...


class ConversationRepository(Protocol[TransactionT]):
    def get_conversation(
        self, session: TransactionT, conversation_id: UUID, *, lock: bool = False
    ) -> ConversationRecord | None: ...

    def list_conversations(
        self, session: TransactionT, project_id: UUID
    ) -> tuple[ConversationRecord, ...]: ...

    def create_top(
        self, session: TransactionT, project_id: UUID, title: str, account_id: UUID
    ) -> ConversationRecord: ...

    def list_messages(
        self, session: TransactionT, conversation_id: UUID, after_seq: int, limit: int
    ) -> tuple[MessageRecord, ...]: ...

    def append_message(
        self,
        session: TransactionT,
        conversation_id: UUID,
        body: str,
        author_kind: AuthorKind,
        author_account_id: UUID | None = None,
        requested_by: UUID | None = None,
        run_id: UUID | None = None,
    ) -> MessageRecord: ...
