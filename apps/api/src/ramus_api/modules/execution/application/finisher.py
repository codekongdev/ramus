"""Terminal transitions shared by the worker and recovery. Each runs in its own transaction."""

import logging
from collections.abc import Mapping
from typing import Any

from ramus_api.modules.execution.application.config import Clock
from ramus_api.modules.execution.application.errors import normalize_failure, run_error
from ramus_api.modules.execution.application.events import RunAnnouncer
from ramus_api.modules.execution.application.ports import RunPurposeHandler
from ramus_api.modules.execution.application.runtime_ports import (
    RunStore,
    TransactionFactory,
    TransactionHooks,
)
from ramus_api.modules.execution.domain.models import RunStatus
from ramus_api.modules.execution.domain.state import RunFailure, RunState, failure_from_exception

logger = logging.getLogger(__name__)


class RunFinisher:
    def __init__(
        self,
        *,
        transaction: TransactionFactory[Any],
        store: RunStore[Any],
        hooks: TransactionHooks[Any],
        handlers: Mapping[str, RunPurposeHandler[Any]],
        announcer: RunAnnouncer,
        clock: Clock,
    ) -> None:
        self._transaction = transaction
        self._store = store
        self._hooks = hooks
        self._handlers = handlers
        self._announcer = announcer
        self._clock = clock

    def succeed(self, state: RunState, output: Mapping[str, Any]) -> None:
        """running -> succeeded with ``complete``; if ``complete`` raises, its writes roll back."""
        try:
            with self._transaction() as session:
                done = self._store.finish(
                    session,
                    state.id,
                    state.attempt,
                    RunStatus.RUNNING,
                    RunStatus.SUCCEEDED,
                    self._clock(),
                    None,
                )
                if done is None:
                    _log_discarded(state, "result")
                    return
                self._handlers[done.purpose].complete(session, done.view, output)
                self._announcer.changed(session, done)
        except Exception as error:  # noqa: BLE001 - recorded as a failed run below
            logger.error("Run completion failed: run_id=%s error=%s", state.id, type(error).__name__)
            self.fail(state, RunStatus.RUNNING, failure_from_exception(error))

    def fail(self, state: RunState, expected: RunStatus, failure: RunFailure) -> RunState | None:
        with self._transaction() as session:
            return self.fail_in(session, state, expected, failure)

    def fail_in(
        self, session: Any, state: RunState, expected: RunStatus, failure: RunFailure
    ) -> RunState | None:
        """Conditional ``expected`` -> failed, then ``handler.fail`` in a savepoint of the same transaction."""
        stored = normalize_failure(failure)
        done = self._store.finish(
            session, state.id, state.attempt, expected, RunStatus.FAILED, self._clock(), stored
        )
        if done is None:
            _log_discarded(state, stored.code)
            return None
        handler = self._handlers.get(done.purpose)
        if handler is not None:
            self._notify_failure(session, handler, done, stored)
        self._announcer.changed(session, done)
        return done

    def _notify_failure(
        self, session: Any, handler: RunPurposeHandler[Any], done: RunState, failure: RunFailure
    ) -> None:
        try:
            with self._hooks.savepoint(session):
                handler.fail(session, done.view, run_error(failure))
        except Exception as error:  # noqa: BLE001 - the run stays failed; the handler's writes roll back
            logger.error("Run failure handler failed: run_id=%s error=%s", done.id, type(error).__name__)


def _log_discarded(state: RunState, outcome: str) -> None:
    logger.info(
        "Run outcome discarded because the run changed meanwhile: run_id=%s attempt=%s outcome=%s",
        state.id,
        state.attempt,
        outcome,
    )
