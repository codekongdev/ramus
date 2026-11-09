"""SQL conversation persistence. All message writers lock before allocating a database sequence."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.conversations.domain.errors import ConversationNotFound
from ramus_api.modules.conversations.domain.models import AuthorKind, ConversationOrigin, NewChildConversation
from ramus_api.modules.conversations.domain.views import ConversationRecord, MessageRecord, validate_text
from ramus_api.modules.conversations.infrastructure.models import ConversationRow, MessageRow
from ramus_api.shared.domain.primitives import new_id


def conversation_record(row: ConversationRow) -> ConversationRecord:
    return ConversationRecord(
        row.id, row.project_id, row.parent_id, row.task_id, row.title, row.created_by, row.created_at
    )


def message_record(row: MessageRow) -> MessageRecord:
    return MessageRecord(
        row.id,
        row.conversation_id,
        row.seq,
        AuthorKind(row.author_kind),
        row.author_account_id,
        row.example_author_label,
        row.body,
        row.requested_by,
        row.run_id,
        row.created_at,
    )


class SqlConversationRepository:
    def get_conversation(
        self, session: Session, conversation_id: UUID, *, lock: bool = False
    ) -> ConversationRecord | None:
        statement = select(ConversationRow).where(ConversationRow.id == conversation_id)
        if lock:
            statement = statement.with_for_update()
        row = session.scalar(statement)
        return None if row is None else conversation_record(row)

    def list_conversations(self, session: Session, project_id: UUID) -> tuple[ConversationRecord, ...]:
        rows = session.scalars(
            select(ConversationRow)
            .where(ConversationRow.project_id == project_id)
            .order_by(ConversationRow.created_at, ConversationRow.id)
        )
        return tuple(conversation_record(row) for row in rows)

    def create_top(
        self, session: Session, project_id: UUID, title: str, account_id: UUID
    ) -> ConversationRecord:
        row = ConversationRow(
            id=new_id(),
            project_id=project_id,
            parent_id=None,
            task_id=None,
            title=validate_text(title, 100),
            origin=ConversationOrigin.TOP.value,
            created_by=account_id,
        )
        session.add(row)
        session.flush()
        return conversation_record(row)

    def create_child(self, session: Session, child: NewChildConversation) -> ConversationRecord:
        parent = self.get_conversation(session, child.parent_id)
        if parent is None or parent.project_id != child.project_id:
            raise ConversationNotFound()
        row = ConversationRow(
            id=new_id(),
            project_id=child.project_id,
            parent_id=child.parent_id,
            task_id=child.task_id,
            title=validate_text(child.title, 100),
            origin=ConversationOrigin.BRANCH.value,
            created_by=child.created_by,
        )
        session.add(row)
        session.flush()
        return conversation_record(row)

    def list_messages(
        self, session: Session, conversation_id: UUID, after_seq: int, limit: int
    ) -> tuple[MessageRecord, ...]:
        rows = session.scalars(
            select(MessageRow)
            .where(MessageRow.conversation_id == conversation_id, MessageRow.seq > after_seq)
            .order_by(MessageRow.seq)
            .limit(limit)
        )
        return tuple(message_record(row) for row in rows)

    def append_message(
        self,
        session: Session,
        conversation_id: UUID,
        body: str,
        author_kind: AuthorKind,
        author_account_id: UUID | None = None,
        requested_by: UUID | None = None,
        run_id: UUID | None = None,
    ) -> MessageRecord:
        # A cursor must never pass a committed higher seq while an earlier seq is still uncommitted.
        # This lock covers allocation AND commit, for HTTP, AI, and system messages alike.
        if self.get_conversation(session, conversation_id, lock=True) is None:
            raise ConversationNotFound()
        row = MessageRow(
            id=new_id(),
            conversation_id=conversation_id,
            author_kind=author_kind.value,
            author_account_id=author_account_id,
            example_author_label=None,
            body=validate_text(body, 20_000),
            requested_by=requested_by,
            run_id=run_id,
        )
        session.add(row)
        session.flush()
        return message_record(row)
