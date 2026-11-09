"""Public, transaction-bound conversation operations used by follow-up creation."""

from uuid import UUID

from sqlalchemy.orm import Session

from ramus_api.modules.conversations.domain.views import conversation_json
from ramus_api.modules.conversations.infrastructure.repository import SqlConversationRepository


class SqlFollowupConversations:
    def __init__(self) -> None:
        self._repository = SqlConversationRepository()

    def project_id(self, session: Session, conversation_id: UUID) -> UUID | None:
        conversation = self._repository.get_conversation(session, conversation_id)
        return None if conversation is None else conversation.project_id

    def create_root(self, session: Session, project_id: UUID, title: str, actor_id: UUID) -> dict:
        conversation = self._repository.create_top(session, project_id, title, actor_id)
        return conversation_json(conversation, ())
