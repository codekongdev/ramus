"""The executor loop: claim a pending run, pin its inputs, call the model outside any transaction,
and record the outcome with a conditional update so a late result never overwrites newer state.
"""

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ramus_api.modules.execution.application.config import Clock, ExecutorConfig
from ramus_api.modules.execution.application.events import RunAnnouncer
from ramus_api.modules.execution.application.finisher import RunFinisher
from ramus_api.modules.execution.application.inflight import InFlightCalls
from ramus_api.modules.execution.application.ports import ContextProvider, LlmGateway, RunPurposeHandler
from ramus_api.modules.execution.application.recovery import RunRecovery
from ramus_api.modules.execution.application.relay import EventRelay, LoopSignal
from ramus_api.modules.execution.application.runtime_ports import (
    RunStore,
    TransactionFactory,
    TransactionHooks,
)
from ramus_api.modules.execution.domain import errors as codes
from ramus_api.modules.execution.domain.models import LlmRequest, RunStatus
from ramus_api.modules.execution.domain.snapshot import snapshot_from_context
from ramus_api.modules.execution.domain.state import (
    RunFailure,
    RunState,
    credential_failure,
    failure_from_exception,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClaimedRun:
    state: RunState
    request: LlmRequest | None
    failure: RunFailure | None


@dataclass(frozen=True)
class CallOutcome:
    output: Mapping[str, Any] | None = None
    failure: RunFailure | None = None
    aborted: bool = False


ABORTED = CallOutcome(aborted=True)


@dataclass(frozen=True)
class WorkerDependencies:
    transaction: TransactionFactory[Any]
    store: RunStore[Any]
    hooks: TransactionHooks[Any]
    handlers: Mapping[str, RunPurposeHandler[Any]]
    context_provider: ContextProvider[Any]
    gateway: LlmGateway
    announcer: RunAnnouncer
    finisher: RunFinisher
    recovery: RunRecovery
    relay: EventRelay
    wakeup: LoopSignal
    inflight: InFlightCalls
    config: ExecutorConfig
    clock: Clock


class RunWorker:
    def __init__(self, deps: WorkerDependencies) -> None:
        self._deps = deps
        self._config = deps.config

    @property
    def purposes(self) -> frozenset[str]:
        """Only purposes with a registered handler are claimed; others wait and eventually time out."""
        return frozenset(self._deps.handlers)

    async def run_once(self) -> bool:
        """Claims and finishes at most one run. Returns whether a run was claimed."""
        claimed = await asyncio.to_thread(self._claim)
        await self._deps.relay.flush()
        if claimed is None:
            return False
        await self._execute(claimed)
        await self._deps.relay.flush()
        return True

    async def recover(self) -> int:
        count = await asyncio.to_thread(self._deps.recovery.recover)
        await self._deps.relay.flush()
        return count

    async def run_forever(self) -> None:
        """Recovers once, then runs ``concurrency`` claim slots, periodic recovery and event relay."""
        self._deps.wakeup.bind()
        await self._recover_logged()
        idle = self._config.poll_interval.total_seconds()
        async with asyncio.TaskGroup() as group:
            group.create_task(self._deps.relay.run_forever(idle))
            group.create_task(self._maintain())
            for _ in range(self._config.concurrency):
                group.create_task(self._slot())

    async def _slot(self) -> None:
        idle = self._config.poll_interval.total_seconds()
        while True:
            try:
                worked = await self.run_once()
            except Exception as error:  # noqa: BLE001 - keep the slot alive; the run is recovered later
                logger.error("Executor slot iteration failed: error=%s", type(error).__name__)
                worked = False
            if not worked:
                await self._deps.wakeup.wait(idle)

    async def _maintain(self) -> None:
        while True:
            await asyncio.sleep(self._config.maintenance_interval.total_seconds())
            await self._recover_logged()

    async def _recover_logged(self) -> None:
        try:
            await self.recover()
        except Exception as error:  # noqa: BLE001 - retried on the next maintenance tick
            logger.error("Executor recovery failed: error=%s", type(error).__name__)

    # --- claim (one transaction) -----------------------------------------------------------------

    def _claim(self) -> ClaimedRun | None:
        with self._deps.transaction() as session:
            state = self._deps.store.claim_next(session, self.purposes, self._deps.clock())
            if state is None:
                return None
            claimed = self._prepare(session, state)
            self._deps.announcer.changed(session, claimed.state)
            return claimed

    def _prepare(self, session: Any, state: RunState) -> ClaimedRun:
        """Pins the inputs and builds the request from the same context in the claim transaction (AC-17)."""
        handler = self._deps.handlers[state.purpose]
        try:
            with self._deps.hooks.savepoint(session):
                context = self._deps.context_provider.snapshot(session, state.conversation_id)
                snapshot = snapshot_from_context(context)
                pinned = self._deps.store.save_snapshot(session, state.id, state.attempt, snapshot)
                if pinned is None:
                    raise RuntimeError("Claimed run left running before its inputs were pinned")
                request = handler.build_request(session, pinned.view, context)
                if request.message_from_seq is not None:
                    pinned = self._deps.store.save_snapshot(
                        session, state.id, state.attempt, snapshot_from_context(context, request)
                    )
                    if pinned is None:
                        raise RuntimeError("Claimed run left running before its messages were pinned")
        except Exception as error:  # noqa: BLE001 - becomes a failed run, the savepoint is rolled back
            logger.error("Run preparation failed: run_id=%s error=%s", state.id, type(error).__name__)
            return ClaimedRun(state, None, failure_from_exception(error))
        failure = credential_failure(pinned.view, request)
        if failure is not None:
            logger.warning("Run request used another account's credential: run_id=%s", state.id)
            return ClaimedRun(pinned, None, failure)
        return ClaimedRun(pinned, request, None)

    # --- model call (no transaction) -------------------------------------------------------------

    async def _execute(self, claimed: ClaimedRun) -> None:
        finisher, state = self._deps.finisher, claimed.state
        if claimed.request is None:
            failure = claimed.failure or RunFailure(codes.LLM_UNAVAILABLE)
            await asyncio.to_thread(finisher.fail, state, RunStatus.RUNNING, failure)
            return
        outcome = await self._call(state, claimed.request)
        if outcome.aborted:
            logger.info("Model call stopped because the run left running: run_id=%s", state.id)
        elif outcome.failure is not None:
            await asyncio.to_thread(finisher.fail, state, RunStatus.RUNNING, outcome.failure)
        elif outcome.output is not None:
            await asyncio.to_thread(finisher.succeed, state, outcome.output)

    async def _call(self, state: RunState, request: LlmRequest) -> CallOutcome:
        timeout = self._config.llm_timeout.total_seconds()
        call = asyncio.ensure_future(asyncio.wait_for(self._deps.gateway.complete(request), timeout))
        self._deps.inflight.register(state.id, call)
        beat = asyncio.create_task(self._heartbeat(state, call))
        try:
            return CallOutcome(output=await call)
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise  # the worker itself is stopping; recovery will mark the run interrupted
            return ABORTED
        except Exception as error:  # noqa: BLE001 - mapped to a stored error code
            failure = failure_from_exception(error)
            logger.warning(
                "Model call failed: run_id=%s error=%s code=%s", state.id, type(error).__name__, failure.code
            )
            return CallOutcome(failure=failure)
        finally:
            beat.cancel()
            self._deps.inflight.unregister(state.id, call)

    async def _heartbeat(self, state: RunState, call: asyncio.Future[Any]) -> None:
        interval = self._config.heartbeat_interval.total_seconds()
        while not call.done():
            await asyncio.sleep(interval)
            try:
                alive = await asyncio.to_thread(self._touch, state)
            except Exception as error:  # noqa: BLE001 - try again next beat; recovery covers long gaps
                logger.warning("Run heartbeat failed: run_id=%s error=%s", state.id, type(error).__name__)
                continue
            if not alive:
                call.cancel()
                return

    def _touch(self, state: RunState) -> bool:
        with self._deps.transaction() as session:
            return self._deps.store.heartbeat(session, state.id, state.attempt, self._deps.clock())
