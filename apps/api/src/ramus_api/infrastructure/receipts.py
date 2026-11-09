from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import JSON, String, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from ramus_api.infrastructure.database import Base, Database
from ramus_api.shared.domain import BusinessError, canonical_hash, new_id, now_iso


class ReceiptRow(Base):
    __tablename__ = "request_receipts"
    __table_args__ = (UniqueConstraint("actor_id", "scope", "request_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(36), index=True)
    scope: Mapped[str] = mapped_column(String(150))
    request_id: Mapped[str] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40))


def execute_once(
    db: Database,
    actor_id: str,
    scope: str,
    request_id: str,
    payload: dict,
    operation: Callable[[Session], dict],
    authorize: Callable[[Session], None] | None = None,
    authorize_response: Callable[[Session, dict], None] | None = None,
) -> dict:
    fingerprint = canonical_hash(payload)

    def existing(session: Session) -> ReceiptRow | None:
        return session.scalar(
            select(ReceiptRow).where(
                ReceiptRow.actor_id == actor_id,
                ReceiptRow.scope == scope,
                ReceiptRow.request_id == request_id,
            )
        )

    def replay(session: Session, row: ReceiptRow) -> dict:
        if row.fingerprint != fingerprint:
            raise BusinessError("IDEMPOTENCY_CONFLICT", "같은 요청 ID에 다른 입력을 사용할 수 없습니다.", 409)
        if authorize_response:
            authorize_response(session, row.response)
        return row.response

    try:
        with db.transaction() as session:
            if authorize:
                authorize(session)
            if row := existing(session):
                return replay(session, row)
            receipt = ReceiptRow(
                id=new_id(),
                actor_id=actor_id,
                scope=scope,
                request_id=request_id,
                fingerprint=fingerprint,
                response={},
                created_at=now_iso(),
            )
            session.add(receipt)
            session.flush()  # Establish the unique request before any side effects.
            response = operation(session)
            if authorize_response:
                authorize_response(session, response)
            receipt.response = response
            session.flush()
            return response
    except IntegrityError:
        # A competing request may have committed the same logical operation.
        with db.transaction() as session:
            if authorize:
                authorize(session)
            if row := existing(session):
                return replay(session, row)
        raise
