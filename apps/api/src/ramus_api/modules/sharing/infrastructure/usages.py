"""Current pinned conclusions projected as usage relationships."""

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.conversations.public import ConversationRecord
from ramus_api.modules.sharing.domain.models import ResultUsage
from ramus_api.modules.sharing.infrastructure.models import ConversationInputRow


class Conversations(Protocol):
    def list_conversations(self, session: Session, project_id: UUID) -> tuple[ConversationRecord, ...]: ...


class ResultSources(Protocol):
    def source_conversations(self, session: Session, result_ids: tuple[UUID, ...]) -> dict[UUID, UUID]: ...


class SqlResultUsageQuery:
    def __init__(self, conversations: Conversations, results: ResultSources) -> None:
        self._conversations = conversations
        self._results = results

    def list_usages(self, session: Session, project_id: UUID) -> tuple[ResultUsage, ...]:
        conversation_ids = tuple(item.id for item in self._conversations.list_conversations(session, project_id))
        rows = session.execute(
            select(ConversationInputRow.conversation_id, ConversationInputRow.result_id)
            .where(ConversationInputRow.conversation_id.in_(conversation_ids))
            .order_by(ConversationInputRow.created_at, ConversationInputRow.id)
        ).all()
        sources = self._results.source_conversations(session, tuple(row.result_id for row in rows))
        return tuple(
            ResultUsage(sources[row.result_id], row.conversation_id, row.result_id)
            for row in rows if row.result_id in sources
        )
