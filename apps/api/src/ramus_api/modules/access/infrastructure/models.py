"""Private access persistence; credential hashes and ciphertext never form API DTOs."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from ramus_api.shared.infrastructure.database import Base


class AccountRow(Base):
    __tablename__ = "account"
    __table_args__ = (
        CheckConstraint("email = lower(btrim(email)) AND length(email) > 0", name="normalized_email"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MembershipRow(Base):
    __tablename__ = "membership"
    __table_args__ = (CheckConstraint("role = 'editor'", name="valid_role"),)

    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id"), primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailCodeRow(Base):
    __tablename__ = "email_code"
    __table_args__ = (
        CheckConstraint("email = lower(btrim(email)) AND length(email) > 0", name="normalized_email"),
        CheckConstraint("attempts BETWEEN 0 AND 5", name="valid_attempts"),
        Index("ix_email_code_email_created_at", "email", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    code_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailCodeDeliveryRow(Base):
    """Recoverable delivery attempts; no plaintext code or mail-provider response is persisted."""

    __tablename__ = "email_code_delivery"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'sending', 'failed', 'sent')", name="valid_status"),
        CheckConstraint("email = lower(btrim(email)) AND length(email) > 0", name="normalized_email"),
        CheckConstraint("(status = 'sent') = (sent_at IS NOT NULL)", name="sent_timestamp"),
        CheckConstraint("status = 'pending' OR (attempt_id IS NOT NULL AND code_id IS NOT NULL AND "
                        "code_hash IS NOT NULL AND code_created_at IS NOT NULL AND expires_at IS NOT NULL AND "
                        "lease_until IS NOT NULL)", name="attempt_fields"),
        Index("ix_email_code_delivery_email_sending", "email", unique=True, postgresql_where=text("status = 'sending'")),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(16))
    attempt_id: Mapped[UUID | None] = mapped_column(Uuid)
    code_id: Mapped[UUID | None] = mapped_column(Uuid)
    code_hash: Mapped[str | None] = mapped_column(String(255))
    code_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionRow(Base):
    __tablename__ = "session"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id"))
    token_hash: Mapped[str] = mapped_column(String(255), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIConnectionRow(Base):
    __tablename__ = "ai_connection"
    __table_args__ = (
        CheckConstraint("provider = 'openai'", name="valid_provider"),
        CheckConstraint("status IN ('connected', 'invalid')", name="valid_status"),
        CheckConstraint("length(ciphertext) > 0", name="ciphertext_not_empty"),
    )

    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(16))
    ciphertext: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthAttemptRow(Base):
    """Only opaque subject digests are stored, never an IP or submitted code."""

    __tablename__ = "auth_attempt"
    __table_args__ = (Index("ix_auth_attempt_scope_subject_created", "scope", "subject_hash", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    scope: Mapped[str] = mapped_column(String(24))
    subject_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
