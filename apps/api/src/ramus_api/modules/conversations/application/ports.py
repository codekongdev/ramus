from typing import Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.conversations.domain.models import NewChildConversation, NewMessage

TransactionT = TypeVar("TransactionT", contravariant=True)


class ConversationWriter(Protocol[TransactionT]):
    """Writes into the caller's transaction; execution never accesses conversation tables."""

    def append_message(self, session: TransactionT, message: NewMessage) -> UUID: ...

    def create_child(self, session: TransactionT, conversation: NewChildConversation) -> UUID: ...
