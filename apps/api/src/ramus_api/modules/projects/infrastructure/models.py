"""Project persistence, with stable seed identities."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from ramus_api.shared.infrastructure.database import Base


class ProjectRow(Base):
    __tablename__ = "project"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    is_shared_sample: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    seed_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
