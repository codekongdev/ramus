"""Sharing owns its send history and one pinned snapshot per result/destination pair."""

from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ramus_api.modules.results.public import Revision
from ramus_api.modules.sharing.domain.models import InputOrigin
from ramus_api.modules.sharing.domain.records import PinnedInput, ShareOutcome, share_outcome
from ramus_api.modules.sharing.infrastructure.models import ConversationInputRow, ShareRow
from ramus_api.shared.domain.primitives import new_id, utc_now


def _json(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    return value


def _input(row: ConversationInputRow) -> PinnedInput:
    return PinnedInput(row.id, row.conversation_id, row.result_id, row.result_revision_id, row.version,
                       row.title_snapshot, InputOrigin(row.origin), row.created_by, row.created_at)


class SqlSharingRepository:
    def pin(self, session: Session, conversation_id: UUID, revision: Revision, actor_id: UUID) -> ShareOutcome:
        row = session.scalar(select(ConversationInputRow).where(
            ConversationInputRow.conversation_id == conversation_id,
            ConversationInputRow.result_id == revision.result_id,
        ).with_for_update())
        outcome = share_outcome(None if row is None else row.version, revision.version)
        session.execute(insert(ShareRow).values(
            id=new_id(), result_revision_id=revision.id, target_conversation_id=conversation_id, shared_by=actor_id,
        ).on_conflict_do_nothing(index_elements=["result_revision_id", "target_conversation_id"]))
        if outcome in (ShareOutcome.UNCHANGED, ShareOutcome.KEPT_NEWER):
            return outcome
        values = dict(result_revision_id=revision.id, version=revision.version,
                      title_snapshot=revision.title, conclusion_snapshot=revision.conclusion,
                      source_snapshot=_json(asdict(revision.source)), origin="share", created_by=actor_id,
                      updated_at=utc_now())
        if row is None:
            session.add(ConversationInputRow(id=new_id(), conversation_id=conversation_id,
                                             result_id=revision.result_id, **values))
        else:
            for name, value in values.items():
                setattr(row, name, value)
        session.flush()
        return outcome

    def list_inputs(self, session: Session, conversation_id: UUID) -> tuple[PinnedInput, ...]:
        rows = session.scalars(select(ConversationInputRow).where(
            ConversationInputRow.conversation_id == conversation_id,
        ).order_by(ConversationInputRow.created_at, ConversationInputRow.id))
        return tuple(_input(row) for row in rows)
