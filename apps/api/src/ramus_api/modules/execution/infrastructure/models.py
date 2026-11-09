"""Durable queue state and contract-specific active-run uniqueness."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ramus_api.shared.infrastructure.database import Base


class TaskRow(Base):
    __tablename__ = "task"
    __table_args__ = (
        UniqueConstraint("source_run_id", "ordinal"),
        CheckConstraint(
            "status IN ('pending', 'running', 'ready', 'failed', 'cancelled')", name="valid_status"
        ),
        CheckConstraint("source_conversation_id <> child_conversation_id", name="distinct_conversations"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    source_conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversation.id"))
    child_conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversation.id"), unique=True)
    source_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("run.id", use_alter=True, name="fk_task_source_run_id_run")
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(100))
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    current_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("run.id", use_alter=True, name="fk_task_current_run_id_run")
    )
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("account.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RunRow(Base):
    __tablename__ = "run"
    __table_args__ = (
        CheckConstraint("purpose IN ('work', 'summary')", name="valid_purpose"),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')", name="valid_status"
        ),
        CheckConstraint(
            "(purpose = 'work' AND target_id IS NULL) OR (purpose = 'summary' AND target_id IS NOT NULL)",
            name="purpose_target",
        ),
        CheckConstraint("jsonb_typeof(input_snapshot) = 'object'", name="snapshot_is_object"),
        CheckConstraint("attempt > 0", name="positive_attempt"),
        Index(
            "uq_run_active_work_conversation",
            "conversation_id",
            unique=True,
            postgresql_where=text("purpose = 'work' AND status IN ('pending', 'running')"),
        ),
        Index(
            "uq_run_active_summary_target",
            "target_id",
            unique=True,
            postgresql_where=text("purpose = 'summary' AND status IN ('pending', 'running')"),
        ),
        Index("ix_run_status_created_at", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id"))
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversation.id"))
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("task.id"))
    purpose: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("result.id", use_alter=True, name="fk_run_target_id_result")
    )
    status: Mapped[str] = mapped_column(String(16))
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("account.id"))
    credential_account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id"))
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    attempt: Mapped[int] = mapped_column(Integer, server_default="1")
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
