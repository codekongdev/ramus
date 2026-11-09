from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ramus_api.infrastructure.database import Base
from ramus_api.shared.domain import BusinessError


class ConversationRow(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    instructions: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40))


class MessageRow(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("project_id", "sequence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    author_id: Mapped[str] = mapped_column(String(36))
    author_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    sequence: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(40))


def message_view(row: MessageRow) -> dict:
    return {
        key: getattr(row, key)
        for key in ("id", "conversation_id", "author_id", "author_name", "role", "content", "sequence", "created_at")
    }


def conversation_view(row: ConversationRow) -> dict:
    return {key: getattr(row, key) for key in ("id", "title", "instructions", "created_at")}


class ConversationRepository:
    def __init__(self, session: Session):
        self.session = session

    def conversations(self, project_id: str) -> list[dict]:
        return [
            conversation_view(row)
            for row in self.session.scalars(
                select(ConversationRow)
                .where(ConversationRow.project_id == project_id)
                .order_by(ConversationRow.created_at)
            )
        ]

    def messages(self, project_id: str) -> list[dict]:
        return [
            message_view(row)
            for row in self.session.scalars(
                select(MessageRow).where(MessageRow.project_id == project_id).order_by(MessageRow.sequence)
            )
        ]

    def conversation(self, ident: str, project_id: str) -> dict:
        row = self.session.get(ConversationRow, ident)
        if not row or row.project_id != project_id:
            raise BusinessError("NOT_FOUND", "대화를 찾을 수 없습니다.", 404)
        return {**conversation_view(row), "project_id": row.project_id}

    def add_conversation(self, data: dict) -> dict:
        row = ConversationRow(**data)
        self.session.add(row)
        self.session.flush()
        return conversation_view(row)

    def add_message(self, data: dict) -> dict:
        row = MessageRow(**data)
        self.session.add(row)
        self.session.flush()
        return message_view(row)
