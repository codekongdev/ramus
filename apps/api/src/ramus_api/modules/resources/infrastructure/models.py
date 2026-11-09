"""Resource heads and pinned revisions; revision contents are append-only at the repository boundary."""

from datetime import datetime
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
from sqlalchemy.orm import Mapped, mapped_column

from ramus_api.shared.infrastructure.database import Base


class ResourceRow(Base):
    __tablename__ = "resource"
    __table_args__ = (
        CheckConstraint("kind IN ('skill', 'text', 'file')", name="valid_kind"),
        ForeignKeyConstraint(
            ["latest_revision_id", "id"],
            ["resource_revision.id", "resource_revision.resource_id"],
            name="fk_resource_latest_revision",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id"))
    kind: Mapped[str] = mapped_column(String(16))
    latest_revision_id: Mapped[UUID] = mapped_column(Uuid)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("account.id"))
    seed_key: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResourceRevisionRow(Base):
    __tablename__ = "resource_revision"
    __table_args__ = (
        UniqueConstraint("resource_id", "number"),
        UniqueConstraint("id", "resource_id"),
        ForeignKeyConstraint(
            ["base_revision_id", "resource_id"],
            ["resource_revision.id", "resource_revision.resource_id"],
            name="fk_resource_revision_base",
        ),
        CheckConstraint("number > 0", name="positive_number"),
        CheckConstraint(
            "(number = 1 AND base_revision_id IS NULL) OR (number > 1 AND base_revision_id IS NOT NULL)",
            name="number_has_base",
        ),
        CheckConstraint("base_revision_id IS NULL OR base_revision_id <> id", name="not_own_base"),
        CheckConstraint(
            "(instructions IS NOT NULL AND content IS NULL AND file_name IS NULL) OR (instructions IS NULL AND content IS NOT NULL)",
            name="valid_content",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(ForeignKey("resource.id"))
    number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str | None] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64))
    base_revision_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConversationResourceRow(Base):
    __tablename__ = "conversation_resource"
    __table_args__ = (
        ForeignKeyConstraint(
            ["revision_id", "resource_id"],
            ["resource_revision.id", "resource_revision.resource_id"],
            name="fk_conversation_resource_pinned_revision",
        ),
    )

    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversation.id"), primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(ForeignKey("resource.id"), primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(Uuid)
    applied_by: Mapped[UUID] = mapped_column(ForeignKey("account.id"))
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
