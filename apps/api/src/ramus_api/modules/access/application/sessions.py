"""Session use cases: issue a session, resolve the current account, log out, and read ``Me``."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from ramus_api.modules.access.application.ports import (
    AccountStore,
    Clock,
    NewSession,
    SecretSource,
    SessionStore,
    SharedProjectProvider,
    TransactionFactory,
)
from ramus_api.modules.access.domain.codes import hash_session_token, session_expires_at
from ramus_api.modules.access.domain.models import AuthenticatedAccount, MeProfile
from ramus_api.shared.domain import new_id

T = TypeVar("T")


@dataclass(frozen=True)
class IssuedSession:
    token: str = field(repr=False)
    expires_at: datetime
    me: MeProfile


@dataclass(frozen=True)
class ProfileReader(Generic[T]):
    transactions: TransactionFactory[T]
    accounts: AccountStore[T]
    shared_project: SharedProjectProvider[T]
    sessions: SessionStore[T]
    clock: Clock

    def authenticated_me(self, token: str | None) -> MeProfile | None:
        if not token:
            return None
        with self.transactions() as transaction:
            account = self.sessions.find_active(transaction, hash_session_token(token), self.clock.now())
            if account is None:
                return None
            profile = self.accounts.get_profile(transaction, account.account_id)
            if profile is None:
                return None
            status = self.accounts.ai_connection_status(transaction, account.account_id)
            return MeProfile(profile, self.shared_project.project_id, status)

    def get_me(self, account_id: UUID) -> MeProfile:
        with self.transactions() as transaction:
            return self.load_me(transaction, account_id)

    def load_me(self, transaction: T, account_id: UUID) -> MeProfile:
        profile = self.accounts.get_profile(transaction, account_id)
        if profile is None:
            raise LookupError(f"Account {account_id} does not exist")
        status = self.accounts.ai_connection_status(transaction, account_id)
        return MeProfile(profile, self.shared_project.project_id, status)


@dataclass(frozen=True)
class SessionIssuer(Generic[T]):
    transactions: TransactionFactory[T]
    sessions: SessionStore[T]
    profiles: ProfileReader[T]
    clock: Clock
    secrets: SecretSource

    def issue(self, account_id: UUID) -> IssuedSession:
        """Creates a new session; only the token digest is stored."""
        token = self.secrets.new_session_token()
        now = self.clock.now()
        expires_at = session_expires_at(now)
        new_session = NewSession(new_id(), account_id, hash_session_token(token), now, expires_at)
        with self.transactions() as transaction:
            self.sessions.add(transaction, new_session)
            me = self.profiles.load_me(transaction, account_id)
        return IssuedSession(token, expires_at, me)


@dataclass(frozen=True)
class Authenticator(Generic[T]):
    transactions: TransactionFactory[T]
    sessions: SessionStore[T]
    clock: Clock

    def authenticate(self, token: str | None) -> AuthenticatedAccount | None:
        if not token:
            return None
        with self.transactions() as transaction:
            return self.sessions.find_active(transaction, hash_session_token(token), self.clock.now())

    def logout(self, token: str | None) -> None:
        """Revokes the session behind ``token``. Missing, unknown, or revoked tokens are a no-op."""
        if not token:
            return
        with self.transactions() as transaction:
            self.sessions.revoke(transaction, hash_session_token(token), self.clock.now())
