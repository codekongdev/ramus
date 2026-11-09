"""Sharing-owned pinned example inputs and cross-project preservation checks."""

from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from ramus_api.modules.sharing.infrastructure.models import ConversationInputRow, ShareRow


class SampleSharing:
    def add(
        self, session: Session, *, identifier: UUID, input_id: UUID, conversation_id: UUID,
        result_id: UUID, revision_id: UUID, title: str, conclusion: str, source: dict, author_id: UUID,
    ) -> None:
        session.add(ShareRow(
            id=identifier, result_revision_id=revision_id,
            target_conversation_id=conversation_id, shared_by=author_id,
        ))
        session.add(ConversationInputRow(
            id=input_id, conversation_id=conversation_id, result_id=result_id,
            result_revision_id=revision_id, version=1, title_snapshot=title,
            conclusion_snapshot=conclusion, source_snapshot=source, origin="share", created_by=author_id,
        ))
        session.flush()

    def clear(
        self, session: Session, conversation_ids: tuple[UUID, ...],
        result_ids: tuple[UUID, ...], revision_ids: tuple[UUID, ...],
    ) -> None:
        external_input = session.scalar(select(ConversationInputRow.id).where(
            ConversationInputRow.result_id.in_(result_ids),
            ConversationInputRow.conversation_id.not_in(conversation_ids),
        ).limit(1))
        external_share = session.scalar(select(ShareRow.id).where(
            ShareRow.result_revision_id.in_(revision_ids),
            ShareRow.target_conversation_id.not_in(conversation_ids),
        ).limit(1))
        if external_input is not None or external_share is not None:
            raise RuntimeError("Sample reset refused: another project uses sample conclusions")
        session.execute(delete(ConversationInputRow).where(or_(
            ConversationInputRow.conversation_id.in_(conversation_ids), ConversationInputRow.result_id.in_(result_ids),
        )))
        session.execute(delete(ShareRow).where(or_(
            ShareRow.target_conversation_id.in_(conversation_ids), ShareRow.result_revision_id.in_(revision_ids),
        )))
