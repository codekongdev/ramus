"""Rolling limits apply across challenges and include verification response replays."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Generic, Protocol, TypeVar

from ramus_api.modules.access.application.errors import AUTH_RATE_LIMITED, AccessRejected
from ramus_api.modules.access.application.ports import Clock, TransactionFactory
from ramus_api.modules.access.domain.codes import hash_code, to_iso_utc

T = TypeVar("T")
RATE_WINDOW = timedelta(hours=1)
REQUEST_EMAIL_LIMIT = 10
REQUEST_IP_LIMIT = 60
VERIFY_EMAIL_LIMIT = 30
VERIFY_IP_LIMIT = 300
SESSION_REISSUE_LIMIT = 3


class AttemptStore(Protocol[T]):
    def reserve(
        self, transaction: T, scope: str, limits: list[tuple[str, int]], now: datetime
    ) -> datetime | None: ...


@dataclass(frozen=True)
class AuthRateLimiter(Generic[T]):
    transactions: TransactionFactory[T]
    attempts: AttemptStore[T]
    clock: Clock
    secret: str = field(repr=False)

    def check(self, scope: str, email: str, ip: str, *, key: str | None = None) -> None:
        if scope == "request":
            subjects = [(f"email:{email}", REQUEST_EMAIL_LIMIT), (f"ip:{ip}", REQUEST_IP_LIMIT)]
        elif scope == "verify":
            subjects = [(f"email:{email}", VERIFY_EMAIL_LIMIT), (f"ip:{ip}", VERIFY_IP_LIMIT)]
        else:
            subjects = [(f"receipt:{email}:{key}", SESSION_REISSUE_LIMIT)]
        limits = [(hash_code(subject, scope, self.secret), limit) for subject, limit in subjects]
        with self.transactions() as transaction:
            available_at = self.attempts.reserve(transaction, scope, limits, self.clock.now())
        if available_at is not None:
            raise AccessRejected(AUTH_RATE_LIMITED, {"resend_available_at": to_iso_utc(available_at)})
