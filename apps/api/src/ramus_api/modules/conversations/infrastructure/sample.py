"""Conversation-owned preparation and maintenance operations for the operator CLI."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ramus_api.modules.conversations.domain.views import validate_text
from ramus_api.modules.conversations.infrastructure.models import ConversationRow, MessageRow


class SampleConversations:
    def add(
        self, session: Session, *, identifier: UUID, project_id: UUID, title: str,
        author_id: UUID, seed_key: str, created_at: datetime,
        parent_id: UUID | None = None, task_id: UUID | None = None,
    ) -> None:
        session.add(ConversationRow(
            id=identifier, project_id=project_id, title=validate_text(title, 100),
            created_by=author_id, seed_key=seed_key, created_at=created_at,
            parent_id=parent_id, task_id=task_id, origin="branch" if task_id else "top",
        ))
        session.flush()

    def message(
        self, session: Session, *, identifier: UUID, conversation_id: UUID,
        author_id: UUID, author_label: str, body: str, created_at: datetime,
    ) -> int:
        row = MessageRow(
            id=identifier, conversation_id=conversation_id, author_kind="human",
            author_account_id=author_id, example_author_label=author_label,
            body=validate_text(body, 20_000), created_at=created_at,
        )
        session.add(row)
        session.flush()
        return row.seq

    def ids(self, session: Session, project_ids: tuple[UUID, ...]) -> tuple[UUID, ...]:
        return tuple(session.scalars(select(ConversationRow.id).where(ConversationRow.project_id.in_(project_ids))))

    def clear(self, session: Session, conversation_ids: tuple[UUID, ...]) -> None:
        session.execute(delete(MessageRow).where(MessageRow.conversation_id.in_(conversation_ids)))
        session.execute(delete(ConversationRow).where(ConversationRow.id.in_(conversation_ids)))

    def clear_messages(self, session: Session, conversation_ids: tuple[UUID, ...]) -> None:
        session.execute(delete(MessageRow).where(MessageRow.conversation_id.in_(conversation_ids)))
