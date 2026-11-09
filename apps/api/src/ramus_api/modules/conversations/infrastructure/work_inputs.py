"""Server-ordered work input, cut off at the original request rather than the latest message."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.conversations.domain.models import AuthorKind
from ramus_api.modules.conversations.infrastructure.models import ConversationRow, MessageRow
from ramus_api.modules.execution.domain.work import WorkHistory, WorkMessage


class SqlWorkInputReader:
    def read(self, session: Session, conversation_id: UUID, run_id: UUID) -> WorkHistory:
        conversation = session.get(ConversationRow, conversation_id)
        if conversation is None:
            raise ValueError("Work conversation does not exist")
        cutoff = session.execute(
            select(MessageRow.seq).where(
                MessageRow.conversation_id == conversation_id,
                MessageRow.run_id == run_id,
                MessageRow.author_kind.in_((AuthorKind.HUMAN.value, AuthorKind.SYSTEM.value)),
            )
        ).scalar_one()
        rows = session.execute(
            select(MessageRow)
            .where(MessageRow.conversation_id == conversation_id, MessageRow.seq <= cutoff)
            .order_by(MessageRow.seq)
        ).scalars()
        messages = tuple(
            WorkMessage(row.seq, AuthorKind(row.author_kind), row.body, row.run_id) for row in rows
        )
        return WorkHistory(
            conversation.project_id,
            conversation.task_id,
            conversation.parent_id is not None or conversation.origin == "branch",
            messages,
        )

    def lock_parent(self, session: Session, conversation_id: UUID) -> None:
        session.execute(
            select(ConversationRow.id).where(ConversationRow.id == conversation_id).with_for_update()
        ).scalar_one()
