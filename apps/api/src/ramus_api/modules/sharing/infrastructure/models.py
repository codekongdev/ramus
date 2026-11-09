"""Share history and the current pinned input per result/destination pair."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
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


class ShareRow(Base):
    __tablename__ = "share"
    __table_args__ = (UniqueConstraint("result_revision_id", "target_conversation_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    result_revision_id: Mapped[UUID] = mapped_column(ForeignKey("result_revision.id"))
    target_conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversation.id"))
    shared_by: Mapped[UUID] = mapped_column(ForeignKey("account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConversationInputRow(Base):
    __tablename__ = "conversation_input"
    __table_args__ = (
        UniqueConstraint("conversation_id", "result_id"),
        ForeignKeyConstraint(
            ["result_revision_id", "result_id", "version"],
            ["result_revision.id", "result_revision.result_id", "result_revision.version"],
            name="fk_conversation_input_pinned_revision",
        ),
        CheckConstraint("origin IN ('share', 'new_conversation')", name="valid_origin"),
        CheckConstraint("jsonb_typeof(source_snapshot) = 'object'", name="source_snapshot_is_object"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversation.id"))
    result_id: Mapped[UUID] = mapped_column(ForeignKey("result.id"))
    result_revision_id: Mapped[UUID] = mapped_column(Uuid)
    version: Mapped[int] = mapped_column(Integer)
    title_snapshot: Mapped[str] = mapped_column(String(100))
    conclusion_snapshot: Mapped[str] = mapped_column(Text)
    source_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    origin: Mapped[str] = mapped_column(String(20))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("account.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
