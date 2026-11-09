"""Supported conversation queries and offline sample maintenance."""

from uuid import UUID

from sqlalchemy.orm import Session

from ramus_api.modules.conversations.domain.views import ConversationRecord
from ramus_api.modules.conversations.infrastructure.repository import SqlConversationRepository
from ramus_api.modules.conversations.infrastructure.sample import SampleConversations as SampleConversations

__all__ = ["ConversationReader", "ConversationRecord", "SampleConversations"]


class ConversationReader:
    """Read-only conversation boundary; mutation APIs remain conversation-owned."""

    def __init__(self) -> None:
        self._repository = SqlConversationRepository()

    def get_conversation(self, session: Session, conversation_id: UUID) -> ConversationRecord | None:
        return self._repository.get_conversation(session, conversation_id)
