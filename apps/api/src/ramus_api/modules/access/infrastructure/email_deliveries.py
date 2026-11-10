"""SQL delivery reservations; called with the access-owned per-email transaction lock."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ramus_api.modules.access.application.email_delivery import DeliveryClaim
from ramus_api.modules.access.application.errors import (
    AUTH_CODE_EXPIRED,
    AUTH_RATE_LIMITED,
    SERVICE_UNAVAILABLE,
    AccessRejected,
)
from ramus_api.modules.access.application.ports import NewEmailCode
from ramus_api.modules.access.domain.codes import can_resend, resend_available_at, to_iso_utc
from ramus_api.modules.access.infrastructure.models import EmailCodeDeliveryRow, EmailCodeRow
from ramus_api.modules.access.infrastructure.stores import SqlEmailCodeStore


class SqlEmailDeliveryStore:
    def prepare(self, transaction: Session, delivery_id: UUID, email: str, now: datetime) -> None:
        transaction.add(EmailCodeDeliveryRow(id=delivery_id, email=email, status="pending", created_at=now))
        transaction.flush()

    def claim(
        self, transaction: Session, delivery_id: UUID, email: str, code: NewEmailCode,
        attempt_id: UUID, now: datetime, lease_until: datetime,
    ) -> DeliveryClaim:
        row = transaction.get(EmailCodeDeliveryRow, delivery_id)
        if row is None or row.email != email:
            raise AccessRejected(SERVICE_UNAVAILABLE)
        if row.status == "sent":
            return DeliveryClaim(None, resend_available_at(row.sent_at))
        latest = SqlEmailCodeStore().latest_created_at(transaction, email)
        if latest is not None and latest >= row.created_at:
            # A failed older action cannot later invalidate a newer successfully sent code.
            raise AccessRejected(AUTH_CODE_EXPIRED)
        if not can_resend(latest, now):
            raise AccessRejected(AUTH_RATE_LIMITED, {"resend_available_at": to_iso_utc(resend_available_at(latest))})
        active = transaction.scalar(select(EmailCodeDeliveryRow).where(
            EmailCodeDeliveryRow.email == email, EmailCodeDeliveryRow.status == "sending",
        ))
        if active is not None:
            if active.lease_until > now:
                raise AccessRejected(SERVICE_UNAVAILABLE)
            active.status = "failed"
            transaction.flush()  # Release the partial unique index before assigning a new sender.
        row.status, row.attempt_id = "sending", attempt_id
        row.code_id, row.code_hash = code.id, code.code_hash
        row.code_created_at, row.expires_at = code.created_at, code.expires_at
        row.lease_until = lease_until
        transaction.flush()
        return DeliveryClaim(attempt_id)

    def complete(self, transaction: Session, delivery_id: UUID, attempt_id: UUID, now: datetime) -> datetime | None:
        row = transaction.get(EmailCodeDeliveryRow, delivery_id)
        if row is None or row.status != "sending" or row.attempt_id != attempt_id:
            return None
        if now >= row.expires_at:
            row.status = "failed"
            return None
        transaction.add(EmailCodeRow(
            id=row.code_id, email=row.email, code_hash=row.code_hash, created_at=now,
            expires_at=row.expires_at, attempts=0,
        ))
        row.status, row.sent_at = "sent", now
        transaction.flush()
        return resend_available_at(now)

    def fail(self, transaction: Session, delivery_id: UUID, attempt_id: UUID) -> None:
        transaction.execute(update(EmailCodeDeliveryRow).where(
            EmailCodeDeliveryRow.id == delivery_id, EmailCodeDeliveryRow.status == "sending",
            EmailCodeDeliveryRow.attempt_id == attempt_id,
        ).values(status="failed"))
