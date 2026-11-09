"""SQL source of a conversation's pinned resource revisions (B3)."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, insert, literal, select
from sqlalchemy.orm import Session

from ramus_api.modules.resources.application.context import PinnedRevision
from ramus_api.modules.resources.domain.models import ResourceKind
from ramus_api.modules.resources.infrastructure.models import (
    ConversationResourceRow,
    ResourceRevisionRow,
    ResourceRow,
)


class SqlPinnedRevisionSource:
    def pinned(self, session: Session, conversation_id: UUID) -> Sequence[PinnedRevision]:
        # Joins on the pinned revision_id, never on resource.latest_revision_id.
        rows = session.execute(
            select(
                ConversationResourceRow.resource_id,
                ResourceRevisionRow.id,
                ResourceRow.kind,
                ResourceRevisionRow.name,
                ResourceRevisionRow.instructions,
                ResourceRevisionRow.content,
            )
            .join(ResourceRevisionRow, ResourceRevisionRow.id == ConversationResourceRow.revision_id)
            .join(ResourceRow, ResourceRow.id == ConversationResourceRow.resource_id)
            .where(ConversationResourceRow.conversation_id == conversation_id)
        ).all()
        return [
            PinnedRevision(r.resource_id, r.id, ResourceKind(r.kind), r.name, r.instructions, r.content)
            for r in rows
        ]

    def copy_pins(self, session: Session, source_conversation_id: UUID, target_conversation_id: UUID) -> None:
        """Replaces the target's pins with the source's. ``applied_by`` keeps who pinned it in the parent."""
        session.execute(
            delete(ConversationResourceRow).where(
                ConversationResourceRow.conversation_id == target_conversation_id
            )
        )
        session.execute(
            insert(ConversationResourceRow).from_select(
                ["conversation_id", "resource_id", "revision_id", "applied_by"],
                select(
                    literal(target_conversation_id, ConversationResourceRow.conversation_id.type),
                    ConversationResourceRow.resource_id,
                    ConversationResourceRow.revision_id,
                    ConversationResourceRow.applied_by,
                ).where(ConversationResourceRow.conversation_id == source_conversation_id),
            )
        )
