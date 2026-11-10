"""One-time password setup proven by an existing active session; no account can be claimed by email."""

from dataclasses import dataclass, field
from typing import Generic, TypeVar

from ramus_api.modules.access.application.errors import PASSWORD_ALREADY_SET, UNAUTHORIZED, AccessRejected
from ramus_api.modules.access.application.ports import (
    Clock,
    PasswordHasher,
    PasswordSetupAccounts,
    PasswordSetupSessions,
    TransactionFactory,
)
from ramus_api.modules.access.application.rate_limits import AuthRateLimiter
from ramus_api.modules.access.domain.codes import hash_code
from ramus_api.modules.access.domain.models import AuthenticatedAccount
from ramus_api.shared.application import IdempotentExecutor

T = TypeVar("T")


@dataclass(frozen=True)
class PasswordSetup(Generic[T]):
    transactions: TransactionFactory[T]
    accounts: PasswordSetupAccounts[T]
    sessions: PasswordSetupSessions[T]
    hasher: PasswordHasher
    idempotency: IdempotentExecutor[T]
    clock: Clock
    limits: AuthRateLimiter[T]
    secret: str = field(repr=False)

    def _require_active(self, transaction: T, account: AuthenticatedAccount) -> None:
        state = self.sessions.lock_for_account(transaction, account.session_id, account.account_id)
        # Check time after obtaining the row lock, which may have waited across expiry.
        if state is None or state.revoked_at is not None or state.expires_at <= self.clock.now():
            raise AccessRejected(UNAUTHORIZED)

    def status(self, account: AuthenticatedAccount) -> bool:
        with self.transactions() as transaction:
            self._require_active(transaction, account)
            configured = self.accounts.password_configured(transaction, account.account_id)
            if configured is None:
                raise AccessRejected(UNAUTHORIZED)
            return configured

    def set_password(self, account: AuthenticatedAccount, password: str, key: str, ip: str) -> dict:
        self.limits.check("password_setup", account.email, ip)
        with self.transactions() as transaction:
            self._require_active(transaction, account)
        encoded = self.hasher.hash(password)  # No DB lock or transaction during the KDF.

        def setup(transaction: T) -> dict:
            self._require_active(transaction, account)
            if not self.accounts.set_initial_password(transaction, account.account_id, encoded):
                raise AccessRejected(PASSWORD_ALREADY_SET)
            return {"configured": True}

        result = self.idempotency.execute_once(
            str(account.account_id), f"access.password_setup:{account.session_id}", key,
            {"password_hmac": hash_code(password, "password_setup", self.secret)}, setup,
        )
        # A generic receipt replay skips the operation. Reauthorize before returning its result,
        # including after logout/expiry during the KDF or a wait on a concurrent receipt.
        with self.transactions() as transaction:
            self._require_active(transaction, account)
        return result
