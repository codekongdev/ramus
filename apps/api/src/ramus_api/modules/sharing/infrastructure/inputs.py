"""Sharing owns all writes and snapshot reads of conversation_input."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.results.public import ApprovedConclusion
from ramus_api.modules.sharing.application.followups import PinnedConclusion
from ramus_api.modules.sharing.infrastructure.models import ConversationInputRow
from ramus_api.shared.domain.primitives import new_id


def pinned(row: ConversationInputRow) -> PinnedConclusion:
    return PinnedConclusion(
        row.id, row.conversation_id, row.result_id, row.result_revision_id, row.version,
        row.title_snapshot, row.conclusion_snapshot, dict(row.source_snapshot), row.origin,
        row.created_by, row.created_at,
    )


class SqlConversationInputs:
    def received(self, session: Session, revision_id: UUID) -> tuple[PinnedConclusion, ...]:
        return tuple(pinned(row) for row in session.scalars(
            select(ConversationInputRow).where(ConversationInputRow.result_revision_id == revision_id)
            .order_by(ConversationInputRow.created_at, ConversationInputRow.id)
        ))

    def list(self, session: Session, conversation_id: UUID) -> tuple[PinnedConclusion, ...]:
        return tuple(pinned(row) for row in session.scalars(
            select(ConversationInputRow).where(ConversationInputRow.conversation_id == conversation_id)
            .order_by(ConversationInputRow.created_at, ConversationInputRow.id)
        ))

    def add(self, session: Session, conversation_id: UUID, revision: ApprovedConclusion, actor_id: UUID) -> None:
        session.add(ConversationInputRow(
            id=new_id(), conversation_id=conversation_id, result_id=revision.result_id,
            result_revision_id=revision.id, version=revision.version, title_snapshot=revision.title,
            conclusion_snapshot=revision.conclusion, source_snapshot=revision.source,
            origin="new_conversation", created_by=actor_id,
        ))
        session.flush()
