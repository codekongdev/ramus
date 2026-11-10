"""SQLAlchemy implementations of the access store ports. Every method runs in the caller's session."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ramus_api.modules.access.application.ports import (
    NewEmailCode,
    NewSession,
    PasswordAccount,
    PasswordSetupSession,
)
from ramus_api.modules.access.domain.codes import EmailCodeState
from ramus_api.modules.access.domain.models import (
    AccountProfile,
    AIConnectionStatus,
    AuthenticatedAccount,
    MembershipRole,
)
from ramus_api.modules.access.infrastructure.models import (
    AccountRow,
    AIConnectionRow,
    EmailCodeRow,
    MembershipRow,
    SessionRow,
)
from ramus_api.shared.domain import new_id

# First key of the two-key advisory lock, so email-code locks never collide with other lock users.
EMAIL_CODE_LOCK_NAMESPACE = 0x52414D01


class SqlEmailCodeStore:
    def lock_email(self, transaction: Session, email: str) -> None:
        transaction.execute(
            text("SELECT pg_advisory_xact_lock(:namespace, hashtext(:email))"),
            {"namespace": EMAIL_CODE_LOCK_NAMESPACE, "email": email},
        )

    def latest_created_at(self, transaction: Session, email: str) -> datetime | None:
        statement = select(func.max(EmailCodeRow.created_at)).where(EmailCodeRow.email == email)
        return transaction.scalar(statement)

    def add(self, transaction: Session, code: NewEmailCode) -> None:
        transaction.add(
            EmailCodeRow(
                id=code.id,
                email=code.email,
                code_hash=code.code_hash,
                expires_at=code.expires_at,
                attempts=0,
                consumed_at=None,
                created_at=code.created_at,
            )
        )
        transaction.flush()

    def lock_latest(self, transaction: Session, email: str) -> EmailCodeState | None:
        statement = (
            select(EmailCodeRow)
            .where(EmailCodeRow.email == email)
            .order_by(EmailCodeRow.created_at.desc(), EmailCodeRow.id.desc())
            .limit(1)
            .with_for_update()
        )
        row = transaction.scalar(statement)
        if row is None:
            return None
        return EmailCodeState(row.id, row.code_hash, row.expires_at, row.attempts, row.consumed_at)

    def record_failed_attempt(self, transaction: Session, code_id: UUID) -> None:
        transaction.execute(
            update(EmailCodeRow).where(EmailCodeRow.id == code_id).values(attempts=EmailCodeRow.attempts + 1)
        )

    def consume(self, transaction: Session, code_id: UUID, at: datetime) -> None:
        transaction.execute(update(EmailCodeRow).where(EmailCodeRow.id == code_id).values(consumed_at=at))


class SqlAccountStore:
    def password_configured(self, transaction: Session, account_id: UUID) -> bool | None:
        return transaction.scalar(select(AccountRow.password_hash.is_not(None)).where(AccountRow.id == account_id))

    def set_initial_password(self, transaction: Session, account_id: UUID, password_hash: str) -> bool:
        account = transaction.scalar(update(AccountRow).where(
            AccountRow.id == account_id, AccountRow.password_hash.is_(None),
        ).values(password_hash=password_hash).returning(AccountRow.id))
        return account is not None

    def find_password_account(self, transaction: Session, email: str) -> PasswordAccount | None:
        row = transaction.execute(select(AccountRow.id, AccountRow.password_hash).where(AccountRow.email == email)).one_or_none()
        return None if row is None else PasswordAccount(row.id, row.password_hash)

    def create_password_account(
        self, transaction: Session, email: str, display_name: str, password_hash: str
    ) -> UUID | None:
        return transaction.scalar(insert(AccountRow).values(
            id=new_id(), email=email, display_name=display_name, password_hash=password_hash,
        ).on_conflict_do_nothing(index_elements=[AccountRow.email]).returning(AccountRow.id))

    def ensure_account(self, transaction: Session, email: str, display_name: str) -> UUID:
        transaction.execute(
            insert(AccountRow)
            .values(id=new_id(), email=email, display_name=display_name)
            .on_conflict_do_nothing(index_elements=[AccountRow.email])
        )
        account_id = transaction.scalar(select(AccountRow.id).where(AccountRow.email == email))
        if account_id is None:
            raise RuntimeError("Account upsert returned no row")
        return account_id

    def add_membership(
        self, transaction: Session, account_id: UUID, project_id: UUID, role: MembershipRole
    ) -> None:
        transaction.execute(
            insert(MembershipRow)
            .values(account_id=account_id, project_id=project_id, role=role.value)
            .on_conflict_do_nothing(index_elements=[MembershipRow.account_id, MembershipRow.project_id])
        )

    def get_profile(self, transaction: Session, account_id: UUID) -> AccountProfile | None:
        row = transaction.get(AccountRow, account_id)
        if row is None:
            return None
        return AccountProfile(row.id, row.email, row.display_name)

    def project_ids(self, transaction: Session, account_id: UUID) -> list[UUID]:
        return list(
            transaction.scalars(
                select(MembershipRow.project_id).where(MembershipRow.account_id == account_id)
            )
        )

    def participants(self, transaction: Session, project_id: UUID) -> list[AccountProfile]:
        rows = transaction.scalars(
            select(AccountRow)
            .join(MembershipRow, MembershipRow.account_id == AccountRow.id)
            .where(MembershipRow.project_id == project_id)
            .order_by(MembershipRow.created_at, AccountRow.id)
        )
        return [AccountProfile(row.id, row.email, row.display_name) for row in rows]

    def ai_connection_status(self, transaction: Session, account_id: UUID) -> AIConnectionStatus:
        status = transaction.scalar(
            select(AIConnectionRow.status).where(AIConnectionRow.account_id == account_id)
        )
        return AIConnectionStatus.NONE if status is None else AIConnectionStatus(status)


class SqlSessionStore:
    def lock_for_account(self, transaction: Session, session_id: UUID, account_id: UUID) -> PasswordSetupSession | None:
        row = transaction.scalar(select(SessionRow).where(
            SessionRow.id == session_id, SessionRow.account_id == account_id,
        ).with_for_update().execution_options(populate_existing=True))
        return None if row is None else PasswordSetupSession(row.expires_at, row.revoked_at)

    def add(self, transaction: Session, session: NewSession) -> None:
        transaction.add(
            SessionRow(
                id=session.id,
                account_id=session.account_id,
                token_hash=session.token_hash,
                expires_at=session.expires_at,
                revoked_at=None,
                created_at=session.created_at,
            )
        )
        transaction.flush()

    def find_active(
        self, transaction: Session, token_hash: str, now: datetime
    ) -> AuthenticatedAccount | None:
        statement = (
            select(SessionRow.id, AccountRow.id, AccountRow.email, AccountRow.display_name)
            .join(AccountRow, AccountRow.id == SessionRow.account_id)
            .where(
                SessionRow.token_hash == token_hash,
                SessionRow.revoked_at.is_(None),
                SessionRow.expires_at > now,
            )
        )
        row = transaction.execute(statement).one_or_none()
        if row is None:
            return None
        session_id, account_id, email, display_name = row
        return AuthenticatedAccount(account_id, email, display_name, session_id)

    def revoke(self, transaction: Session, token_hash: str, at: datetime) -> None:
        transaction.execute(
            update(SessionRow)
            .where(SessionRow.token_hash == token_hash, SessionRow.revoked_at.is_(None))
            .values(revoked_at=at)
        )
