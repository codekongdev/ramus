"""Conversations and server-ordered messages."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ramus_api.shared.infrastructure.database import Base


class ConversationRow(Base):
    __tablename__ = "conversation"
    __table_args__ = (
        CheckConstraint("origin IN ('top', 'branch', 'from_result')", name="valid_origin"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="not_own_parent"),
        Index("ix_conversation_project_id_title", "project_id", "title"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id"))
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("conversation.id"))
    task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "task.id",
            use_alter=True,
            name="fk_conversation_task_id_task",
            deferrable=True,
            initially="DEFERRED",
        )
    )
    title: Mapped[str] = mapped_column(String(100))
    origin: Mapped[str] = mapped_column(String(16))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("account.id"))
    seed_key: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MessageRow(Base):
    __tablename__ = "message"
    __table_args__ = (
        UniqueConstraint("conversation_id", "seq"),
        CheckConstraint("author_kind IN ('human', 'ai', 'system')", name="valid_author_kind"),
        CheckConstraint("length(btrim(body)) BETWEEN 1 AND 20000", name="valid_body"),
        CheckConstraint("seq > 0", name="positive_seq"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversation.id"))
    seq: Mapped[int] = mapped_column(BigInteger, Identity())
    author_kind: Mapped[str] = mapped_column(String(16))
    author_account_id: Mapped[UUID | None] = mapped_column(ForeignKey("account.id"))
    example_author_label: Mapped[str | None] = mapped_column(String(100))
    body: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[UUID | None] = mapped_column(ForeignKey("account.id"))
    run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("run.id", use_alter=True, name="fk_message_run_id_run")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
