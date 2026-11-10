"""Password authentication with protected receipts, bounded replay and account-owned credentials."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Generic, TypeVar

from ramus_api.modules.access.application.errors import (
    ACCOUNT_ALREADY_EXISTS,
    AUTH_INVALID_CREDENTIALS,
    AccessRejected,
)
from ramus_api.modules.access.application.ports import (
    AccountStore,
    Clock,
    PasswordAccountStore,
    PasswordHasher,
    SharedProjectProvider,
    TransactionFactory,
)
from ramus_api.modules.access.application.rate_limits import AuthRateLimiter
from ramus_api.modules.access.application.sessions import IssuedSession, SessionIssuer
from ramus_api.modules.access.domain.codes import hash_code, to_iso_utc
from ramus_api.modules.access.domain.models import MembershipRole
from ramus_api.shared.application import IdempotentExecutor

T = TypeVar("T")


@dataclass(frozen=True)
class PasswordAuthentication(Generic[T]):
    transactions: TransactionFactory[T]
    accounts: PasswordAccountStore[T]
    memberships: AccountStore[T]
    shared_project: SharedProjectProvider[T]
    hasher: PasswordHasher
    idempotency: IdempotentExecutor[T]
    issuer: SessionIssuer[T]
    clock: Clock
    limits: AuthRateLimiter[T]
    secret: str = field(repr=False)

    def register(self, email: str, password: str, display_name: str, key: str, ip: str) -> IssuedSession:
        self.limits.check("register", email, ip)
        password_hash = self.hasher.hash(password)

        def create(transaction: T) -> dict:
            account_id = self.accounts.create_password_account(transaction, email, display_name, password_hash)
            if account_id is None:
                raise AccessRejected(ACCOUNT_ALREADY_EXISTS)
            self._join(transaction, account_id)
            return self._accepted(account_id)

        payload = {"email": email, "display_name": display_name, "password_hmac": hash_code(password, "password", self.secret)}
        outcome = self.idempotency.execute_once("anonymous", "auth.register", key, payload, create)
        return self._issue(email, key, "register", outcome)

    def login(self, email: str, password: str, key: str, ip: str) -> IssuedSession:
        self.limits.check("password_login", email, ip)
        with self.transactions() as transaction:
            account = self.accounts.find_password_account(transaction, email)
        accepted = self.hasher.verify(password, None if account is None else account.password_hash)
        if not accepted or account is None:
            raise AccessRejected(AUTH_INVALID_CREDENTIALS)

        def accept(transaction: T) -> dict:
            self._join(transaction, account.account_id)
            return self._accepted(account.account_id)

        payload = {"email": email, "password_hmac": hash_code(password, "password", self.secret)}
        outcome = self.idempotency.execute_once("anonymous", "auth.password_login", key, payload, accept)
        return self._issue(email, key, "login", outcome)

    def _join(self, transaction: T, account_id) -> None:
        project_id = self.shared_project.ensure_shared_project(transaction)
        self.memberships.add_membership(transaction, account_id, project_id, MembershipRole.EDITOR)
        for followup_id in self.shared_project.existing_followup_project_ids(transaction):
            self.memberships.add_membership(transaction, account_id, followup_id, MembershipRole.EDITOR)

    def _accepted(self, account_id) -> dict:
        return {"account_id": str(account_id), "expires_at": to_iso_utc(self.clock.now() + timedelta(minutes=10))}

    def _issue(self, email: str, key: str, action: str, outcome: dict) -> IssuedSession:
        from uuid import UUID

        if self.clock.now() >= datetime.fromisoformat(outcome["expires_at"]):
            raise AccessRejected(AUTH_INVALID_CREDENTIALS)
        self.limits.check("session", email, "unused", key=f"{action}:{key}")
        return self.issuer.issue(UUID(outcome["account_id"]))
