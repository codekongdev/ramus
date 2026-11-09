"""Account-owned AI connection persistence; no other module reads this table."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ramus_api.modules.access.domain.credentials import StoredCredential
from ramus_api.modules.access.domain.models import AIConnectionStatus
from ramus_api.modules.access.infrastructure.models import AIConnectionRow


class SqlAiConnectionStore:
    def get(self, transaction: Session, account_id: UUID) -> StoredCredential | None:
        row = transaction.get(AIConnectionRow, account_id)
        if row is None:
            return None
        return StoredCredential(row.ciphertext, AIConnectionStatus(row.status), row.verified_at)

    def save(self, transaction: Session, account_id: UUID, credential: StoredCredential) -> None:
        values = {
            "provider": "openai",
            "ciphertext": credential.ciphertext,
            "status": credential.status.value,
            "verified_at": credential.verified_at,
        }
        transaction.execute(
            insert(AIConnectionRow)
            .values(account_id=account_id, **values)
            .on_conflict_do_update(index_elements=[AIConnectionRow.account_id], set_=values)
        )

    def delete(self, transaction: Session, account_id: UUID) -> None:
        transaction.execute(delete(AIConnectionRow).where(AIConnectionRow.account_id == account_id))

    def is_connected(self, transaction: Session, account_id: UUID) -> bool:
        status = transaction.scalar(select(AIConnectionRow.status).where(AIConnectionRow.account_id == account_id))
        return status == AIConnectionStatus.CONNECTED.value
