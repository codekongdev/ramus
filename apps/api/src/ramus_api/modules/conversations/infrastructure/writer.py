"""The public write adapter used by execution; it never commits its caller's transaction."""

from uuid import UUID

from sqlalchemy.orm import Session

from ramus_api.modules.conversations.application.ports import CommittedEvents
from ramus_api.modules.conversations.domain.models import AuthorKind, NewChildConversation, NewMessage
from ramus_api.modules.conversations.domain.views import ancestor_paths, conversation_json
from ramus_api.modules.conversations.infrastructure.repository import SqlConversationRepository
from ramus_api.modules.realtime.domain.events import EventName, ProjectEvent
from ramus_api.shared.domain.primitives import utc_now


class SqlConversationWriter:
    def __init__(self, repository: SqlConversationRepository, events: CommittedEvents[Session]) -> None:
        self._repository = repository
        self._events = events

    def append_message(self, session: Session, message: NewMessage) -> UUID:
        if message.author_kind == AuthorKind.HUMAN:
            raise ValueError("Human messages must use the authenticated conversation use case")
        row = self._repository.append_message(
            session,
            message.conversation_id,
            message.body,
            message.author_kind,
            requested_by=message.requested_by,
            run_id=message.run_id,
        )
        conversation = self._repository.get_conversation(session, message.conversation_id)
        assert conversation is not None
        self._events.after_commit(
            session,
            ProjectEvent(
                conversation.project_id,
                EventName.MESSAGE_CREATED,
                utc_now(),
                {"conversation_id": message.conversation_id, "message_id": row.id, "seq": row.seq},
            ),
        )
        return row.id

    def create_child(self, session: Session, conversation: NewChildConversation) -> UUID:
        row = self._repository.create_child(session, conversation)
        project_conversations = self._repository.list_conversations(session, row.project_id)
        response = conversation_json(row, ancestor_paths(project_conversations)[row.id])
        self._events.after_commit(
            session,
            ProjectEvent(
                row.project_id,
                EventName.CONVERSATION_CREATED,
                utc_now(),
                {"project_id": row.project_id, "conversation": response},
            ),
        )
        return row.id
