"""Executor-internal ports. SQL implementations live in ``execution/infrastructure``.

Every store method runs inside the transaction it receives; the caller decides commit or rollback.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any, Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.execution.domain.models import RunInputSnapshot, RunRequest, RunStatus
from ramus_api.modules.execution.domain.state import RunFailure, RunState

TransactionT = TypeVar("TransactionT", contravariant=True)
TransactionT_co = TypeVar("TransactionT_co", covariant=True)


class TransactionFactory(Protocol[TransactionT_co]):
    """Opens a transaction that commits on normal exit and rolls back on error."""

    def __call__(self) -> AbstractContextManager[TransactionT_co]: ...


class TransactionHooks(Protocol[TransactionT]):
    def after_commit(self, session: TransactionT, callback: Callable[[], None]) -> None:
        """Runs ``callback`` once the outermost transaction commits; drops it if that work rolls back."""

    def savepoint(self, session: TransactionT) -> AbstractContextManager[Any]:
        """Nested transaction: rolled back alone if the block raises, the caller's transaction survives."""


class RunStore(Protocol[TransactionT]):
    def insert(
        self,
        session: TransactionT,
        run_id: UUID,
        request: RunRequest,
        credential_account_id: UUID,
        snapshot: RunInputSnapshot,
    ) -> RunState:
        """Adds a pending run. Raises ``ActiveRunConflict``; the caller's transaction stays usable."""

    def lock(self, session: TransactionT, run_id: UUID) -> RunState | None:
        """Reads the run and row-locks it until the transaction ends."""

    def claim_next(self, session: TransactionT, purposes: frozenset[str], now: datetime) -> RunState | None:
        """Moves the oldest unlocked pending run of ``purposes`` to running."""

    def save_snapshot(
        self, session: TransactionT, run_id: UUID, attempt: int, snapshot: RunInputSnapshot
    ) -> RunState | None: ...

    def heartbeat(self, session: TransactionT, run_id: UUID, attempt: int, now: datetime) -> bool:
        """True while the run is still this attempt and running."""

    def finish(
        self,
        session: TransactionT,
        run_id: UUID,
        attempt: int,
        expected: RunStatus,
        outcome: RunStatus,
        now: datetime,
        failure: RunFailure | None,
    ) -> RunState | None:
        """Conditional transition; ``None`` when the run left ``expected`` or the attempt changed."""

    def cancel(self, session: TransactionT, run_id: UUID, now: datetime) -> RunState | None: ...

    def requeue(self, session: TransactionT, run_id: UUID, now: datetime) -> RunState | None:
        """failed/cancelled -> pending with the next attempt. Raises ``ActiveRunConflict``."""

    def lock_stale_running(self, session: TransactionT, heartbeat_before: datetime) -> RunState | None:
        """One running run whose heartbeat is older than the cutoff, skipping rows locked elsewhere."""

    def lock_expired_pending(self, session: TransactionT, queued_before: datetime) -> RunState | None:
        """One pending run queued before the cutoff, skipping rows locked elsewhere."""
