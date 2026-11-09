"""Generated drafts and approved versions keep their distinct lifecycles."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ramus_api.shared.infrastructure.database import Base


class ResultRow(Base):
    __tablename__ = "result"
    __table_args__ = (
        ForeignKeyConstraint(
            ["latest_revision_id", "id", "latest_version"],
            ["result_revision.id", "result_revision.result_id", "result_revision.version"],
            name="fk_result_latest_revision",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "(latest_revision_id IS NULL AND latest_version = 0) OR (latest_revision_id IS NOT NULL AND latest_version > 0)",
            name="valid_latest_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id"))
    source_conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversation.id"))
    source_task_id: Mapped[UUID] = mapped_column(ForeignKey("task.id"), unique=True)
    title: Mapped[str] = mapped_column(String(100))
    latest_revision_id: Mapped[UUID | None] = mapped_column(Uuid)
    latest_version: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResultDraftRow(Base):
    __tablename__ = "result_draft"
    __table_args__ = (
        CheckConstraint("status IN ('generating', 'ready', 'failed')", name="valid_status"),
        CheckConstraint("base_version >= 0", name="nonnegative_base_version"),
        CheckConstraint(
            "message_from_seq > 0 AND message_to_seq >= message_from_seq", name="valid_message_range"
        ),
    )

    result_id: Mapped[UUID] = mapped_column(ForeignKey("result.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(16))
    conclusion: Mapped[str | None] = mapped_column(Text)
    base_version: Mapped[int] = mapped_column(Integer)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("run.id"))
    message_from_seq: Mapped[int] = mapped_column(BigInteger)
    message_to_seq: Mapped[int] = mapped_column(BigInteger)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResultRevisionRow(Base):
    __tablename__ = "result_revision"
    __table_args__ = (
        UniqueConstraint("result_id", "version"),
        UniqueConstraint("id", "result_id", "version"),
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint("length(btrim(conclusion)) BETWEEN 1 AND 20000", name="valid_conclusion"),
        CheckConstraint("jsonb_typeof(source) = 'object'", name="source_is_object"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    result_id: Mapped[UUID] = mapped_column(ForeignKey("result.id"))
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(100))
    conclusion: Mapped[str] = mapped_column(Text)
    source: Mapped[dict[str, Any]] = mapped_column(JSONB)
    saved_by: Mapped[UUID] = mapped_column(ForeignKey("account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
