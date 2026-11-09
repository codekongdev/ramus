"""Adapters from other modules' public pieces to the resources ports."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.access.application.ports import ProjectAccess
from ramus_api.modules.conversations.infrastructure.models import ConversationRow
from ramus_api.shared.domain.errors import BusinessError


class MembershipFromProjectAccess:
    """``ProjectMembership`` on top of access's public ``ProjectAccess.require_member``."""

    def __init__(self, access: ProjectAccess[Session]) -> None:
        self._access = access

    def is_member(self, session: Session, account_id: UUID, project_id: UUID) -> bool:
        try:
            self._access.require_member(session, project_id, account_id)
        except BusinessError:
            return False
        return True


class SqlConversationDirectory:
    """Read-only project lookup. Replace with a conversations public query when one exists."""

    def project_of(self, session: Session, conversation_id: UUID) -> UUID | None:
        return session.scalar(select(ConversationRow.project_id).where(ConversationRow.id == conversation_id))
