"""Conversation-owned immutable message ranges for summaries."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ramus_api.modules.conversations.domain.models import AuthorKind
from ramus_api.modules.conversations.infrastructure.models import MessageRow
from ramus_api.modules.execution.domain.work import WorkMessage


class SqlSummaryInputReader:
    def bounds(self, session: Session, conversation_id: UUID) -> tuple[int, int] | None:
        start, end = session.execute(
            select(func.min(MessageRow.seq), func.max(MessageRow.seq))
            .where(MessageRow.conversation_id == conversation_id)
        ).one()
        return None if start is None else (start, end)

    def read(
        self, session: Session, conversation_id: UUID, after_seq: int, through_seq: int
    ) -> tuple[WorkMessage, ...]:
        rows = session.scalars(
            select(MessageRow).where(
                MessageRow.conversation_id == conversation_id,
                MessageRow.seq > after_seq,
                MessageRow.seq <= through_seq,
            ).order_by(MessageRow.seq)
        )
        return tuple(WorkMessage(row.seq, AuthorKind(row.author_kind), row.body, row.run_id) for row in rows)
