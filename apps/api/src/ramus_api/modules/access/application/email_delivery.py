"""Short transactional reservations around external login-mail delivery."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.access.application.ports import NewEmailCode

DELIVERY_LEASE = timedelta(minutes=2)
T = TypeVar("T", contravariant=True)


@dataclass(frozen=True)
class DeliveryClaim:
    attempt_id: UUID | None
    resend_available_at: datetime | None = None


class EmailDeliveryStore(Protocol[T]):
    """All methods run under the caller's transaction and email advisory lock."""

    def prepare(self, transaction: T, delivery_id: UUID, email: str, now: datetime) -> None: ...

    def claim(
        self, transaction: T, delivery_id: UUID, email: str, code: NewEmailCode,
        attempt_id: UUID, now: datetime, lease_until: datetime,
    ) -> DeliveryClaim:
        """Replay a sent delivery or reserve one attempt; reject a live lease or stale request."""
        ...

    def complete(self, transaction: T, delivery_id: UUID, attempt_id: UUID, now: datetime) -> datetime | None:
        """Activate the code and mark sent atomically, only if this attempt still owns the lease."""
        ...

    def fail(self, transaction: T, delivery_id: UUID, attempt_id: UUID) -> None:
        """Release only the matching attempt; a later attempt must remain untouched."""
        ...
