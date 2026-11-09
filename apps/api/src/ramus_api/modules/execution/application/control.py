"""Cancel and retry of one run, inside the caller's transaction. Only the requester may act (C7)."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from ramus_api.modules.execution.application.config import Clock
from ramus_api.modules.execution.application.errors import business_error
from ramus_api.modules.execution.application.events import RunAnnouncer
from ramus_api.modules.execution.application.inflight import InFlightCalls
from ramus_api.modules.execution.application.ports import AiConnectionQuery
from ramus_api.modules.execution.application.runtime_ports import RunStore, TransactionHooks
from ramus_api.modules.execution.domain import errors as codes
from ramus_api.modules.execution.domain.errors import ActiveRunConflict
from ramus_api.modules.execution.domain.state import RunState, cancel_denial, retry_denial


class RunControlService:
    def __init__(
        self,
        *,
        store: RunStore[Any],
        connections: AiConnectionQuery[Any],
        hooks: TransactionHooks[Any],
        announcer: RunAnnouncer,
        inflight: InFlightCalls,
        clock: Clock,
    ) -> None:
        self._store = store
        self._connections = connections
        self._hooks = hooks
        self._announcer = announcer
        self._inflight = inflight
        self._clock = clock

    def _locked(self, session: Any, run_id: UUID) -> RunState:
        state = self._store.lock(session, run_id)
        if state is None:
            raise business_error(codes.NOT_FOUND)
        return state

    def cancel(self, session: Any, run_id: UUID, actor_id: UUID) -> RunState:
        """pending/running -> cancelled. A result that arrives later is discarded by the worker."""
        state = self._locked(session, run_id)
        denial = cancel_denial(state, actor_id)
        if denial is not None:
            raise business_error(denial)
        cancelled = self._store.cancel(session, run_id, self._clock())
        if cancelled is None:  # the row is locked, so only a broken invariant gets here
            raise business_error(codes.RUN_NOT_CANCELLABLE)
        self._announcer.changed(session, cancelled)
        abort = self._inflight.capture_abort(run_id)
        self._hooks.after_commit(session, abort)
        return cancelled

    def retry(
        self, session: Any, run_id: UUID, actor_id: UUID,
        *, validate_requeued: Callable[[RunState], None] | None = None,
    ) -> RunState:
        """failed/cancelled -> pending with the next attempt. Inputs are pinned again when claimed."""
        state = self._locked(session, run_id)
        denial = retry_denial(state, actor_id)
        if denial is not None:
            raise business_error(denial)
        if not self._connections.is_connected(session, state.requested_by):
            raise business_error(codes.AI_CONNECTION_REQUIRED)
        try:
            queued = self._store.requeue(session, run_id, self._clock())
        except ActiveRunConflict:
            raise business_error(codes.ACTIVE_RUN_EXISTS) from None
        if queued is None:
            raise business_error(codes.RUN_NOT_RETRYABLE)
        # The caller may validate its current pointer only after requeue acquired the active-run
        # uniqueness lock, before taking projection locks or scheduling events. Raising rolls the
        # whole transaction back, including the requeue and its idempotency receipt.
        if validate_requeued is not None:
            validate_requeued(queued)
        self._announcer.changed(session, queued)
        self._announcer.queued(session)
        return queued
