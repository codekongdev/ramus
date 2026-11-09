from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from ramus_api.infrastructure.database import Base
from ramus_api.shared.domain import BusinessError


class UserRow(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(240))


class SessionRow(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[str] = mapped_column(String(40))


class ProjectRow(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    instructions: Mapped[str] = mapped_column(String(12000))
    next_sequence: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(40))


class MembershipRow(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


def user_view(row: UserRow) -> dict:
    return {"id": row.id, "email": row.email, "name": row.name}


def project_view(row: ProjectRow) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "instructions": row.instructions,
    }


class AccessRepository:
    def __init__(self, session: Session):
        self.session = session

    def credentials(self, email: str) -> dict | None:
        row = self.session.scalar(select(UserRow).where(UserRow.email == email.strip().lower()))
        return {**user_view(row), "password_hash": row.password_hash} if row else None

    def add_session(self, hashed_token: str, user_id: str, expires_at: str) -> None:
        self.session.add(SessionRow(token_hash=hashed_token, user_id=user_id, expires_at=expires_at))

    def user_for_session(self, hashed_token: str, now: str) -> dict | None:
        row = self.session.scalar(
            select(UserRow)
            .join(SessionRow)
            .where(SessionRow.token_hash == hashed_token, SessionRow.expires_at > now)
        )
        return user_view(row) if row else None

    def delete_session(self, hashed_token: str) -> None:
        if row := self.session.get(SessionRow, hashed_token):
            self.session.delete(row)

    def ensure_member(self, user_id: str, project_id: str) -> dict:
        row = self.session.scalar(
            select(ProjectRow)
            .join(MembershipRow)
            .where(ProjectRow.id == project_id, MembershipRow.user_id == user_id)
        )
        if not row:
            raise BusinessError("NOT_FOUND", "프로젝트를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        return project_view(row)

    def projects(self, user_id: str) -> list[dict]:
        return [
            project_view(row)
            for row in self.session.scalars(
                select(ProjectRow)
                .join(MembershipRow)
                .where(MembershipRow.user_id == user_id)
                .order_by(ProjectRow.created_at)
            )
        ]

    def members(self, project_id: str) -> list[dict]:
        return [
            user_view(row)
            for row in self.session.scalars(
                select(UserRow)
                .join(MembershipRow)
                .where(MembershipRow.project_id == project_id)
                .order_by(UserRow.name)
            )
        ]

    def allocate_sequence(self, project_id: str) -> int:
        return self.session.scalar(
            update(ProjectRow)
            .where(ProjectRow.id == project_id)
            .values(next_sequence=ProjectRow.next_sequence + 1)
            .returning(ProjectRow.next_sequence)
        )

    def create_project(self, data: dict, members: list[dict]) -> None:
        self.session.add(ProjectRow(**data))
        self.session.flush()
        self.session.add_all([MembershipRow(**member) for member in members])

    def all_users(self) -> list[dict]:
        return [user_view(row) for row in self.session.scalars(select(UserRow).order_by(UserRow.email))]

    def add_user(self, data: dict) -> None:
        self.session.add(UserRow(**data))
        self.session.flush()
