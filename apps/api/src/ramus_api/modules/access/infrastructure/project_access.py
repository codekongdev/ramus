"""Access-owned implementations used through its public authorization/connection ports."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ramus_api.modules.access.infrastructure.models import AccountRow, AIConnectionRow, MembershipRow
from ramus_api.shared.domain.errors import BusinessError
from ramus_api.shared.presentation.errors import http_error_code


class SqlProjectAccess:
    def require_member(self, transaction: Session, project_id: UUID, account_id: UUID) -> None:
        member = transaction.scalar(
            select(MembershipRow.account_id).where(
                MembershipRow.project_id == project_id, MembershipRow.account_id == account_id
            )
        )
        if member is None:
            code, message = http_error_code(404)
            raise BusinessError(code, message, status=404)

    def display_names(self, transaction: Session, account_ids: set[UUID]) -> dict[UUID, str]:
        if not account_ids:
            return {}
        return dict(transaction.execute(
            select(AccountRow.id, AccountRow.display_name).where(AccountRow.id.in_(account_ids))
        ).all())


class SqlAiConnectionQuery:
    """Reports status only. The A3 credential adapter handles decryption separately."""

    def is_connected(self, session: Session, account_id: UUID) -> bool:
        return session.scalar(
            select(AIConnectionRow.status).where(AIConnectionRow.account_id == account_id)
        ) == "connected"
