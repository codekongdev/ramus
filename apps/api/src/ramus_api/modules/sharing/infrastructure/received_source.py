"""SQL source of the conclusions a conversation received as AI input (B3).

Reads the snapshot stored on ``conversation_input`` (title/conclusion at the pinned version), so a
newer result version never leaks in until it is explicitly sent again (D8).
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.resources.application.context import ReceivedConclusion
from ramus_api.modules.sharing.infrastructure.models import ConversationInputRow


class SqlReceivedConclusionSource:
    def received(self, session: Session, conversation_id: UUID) -> Sequence[ReceivedConclusion]:
        rows = session.execute(
            select(
                ConversationInputRow.result_id,
                ConversationInputRow.result_revision_id,
                ConversationInputRow.version,
                ConversationInputRow.title_snapshot,
                ConversationInputRow.conclusion_snapshot,
            ).where(ConversationInputRow.conversation_id == conversation_id)
        ).all()
        return [ReceivedConclusion(*row) for row in rows]
