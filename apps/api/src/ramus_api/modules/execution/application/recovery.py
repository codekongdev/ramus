"""Restart recovery and the pending-wait limit. Never re-runs anything: a retry needs the user's consent."""

from collections.abc import Callable
from typing import Any

from ramus_api.modules.execution.application.config import Clock, ExecutorConfig
from ramus_api.modules.execution.application.finisher import RunFinisher
from ramus_api.modules.execution.application.runtime_ports import RunStore, TransactionFactory
from ramus_api.modules.execution.domain.models import RunStatus
from ramus_api.modules.execution.domain.state import INTERRUPTED, TIMED_OUT


class RunRecovery:
    """Each run is handled in its own transaction under ``SKIP LOCKED``, so concurrent sweeps never collide."""

    def __init__(
        self,
        *,
        transaction: TransactionFactory[Any],
        store: RunStore[Any],
        finisher: RunFinisher,
        config: ExecutorConfig,
        clock: Clock,
    ) -> None:
        self._transaction = transaction
        self._store = store
        self._finisher = finisher
        self._config = config
        self._clock = clock

    def recover(self) -> int:
        """Fails stale running runs (RUN_INTERRUPTED) and over-long pending runs (RUN_TIMED_OUT)."""
        return self._sweep(self._fail_stale) + self._sweep(self._fail_expired)

    def _sweep(self, step: Callable[[], bool]) -> int:
        count = 0
        while count < self._config.recovery_batch and step():
            count += 1
        return count

    def _fail_stale(self) -> bool:
        with self._transaction() as session:
            state = self._store.lock_stale_running(session, self._clock() - self._config.stale_after)
            if state is None:
                return False
            return self._finisher.fail_in(session, state, RunStatus.RUNNING, INTERRUPTED) is not None

    def _fail_expired(self) -> bool:
        with self._transaction() as session:
            state = self._store.lock_expired_pending(session, self._clock() - self._config.max_pending_wait)
            if state is None:
                return False
            return self._finisher.fail_in(session, state, RunStatus.PENDING, TIMED_OUT) is not None
