"""Wires the executor's services from SQL adapters and injected ports. The app lifespan calls this later."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from ramus_api.modules.execution.application.config import Clock, ExecutorConfig
from ramus_api.modules.execution.application.control import RunControlService
from ramus_api.modules.execution.application.events import RunAnnouncer
from ramus_api.modules.execution.application.finisher import RunFinisher
from ramus_api.modules.execution.application.inflight import InFlightCalls
from ramus_api.modules.execution.application.ports import (
    AiConnectionQuery,
    ContextProvider,
    LlmGateway,
    RunPurposeHandler,
)
from ramus_api.modules.execution.application.recovery import RunRecovery
from ramus_api.modules.execution.application.registration import RunRegistrationService
from ramus_api.modules.execution.application.relay import EventRelay, LoopSignal
from ramus_api.modules.execution.application.runtime_ports import TransactionFactory
from ramus_api.modules.execution.application.worker import RunWorker, WorkerDependencies
from ramus_api.modules.execution.domain.models import RunPurpose
from ramus_api.modules.execution.infrastructure.commit_hooks import SqlAlchemyTransactionHooks
from ramus_api.modules.execution.infrastructure.run_store import SqlRunStore
from ramus_api.modules.realtime.application.ports import EventPublisher
from ramus_api.shared.domain.primitives import utc_now


@dataclass(frozen=True)
class ExecutionRuntime:
    requester: RunRegistrationService
    control: RunControlService
    worker: RunWorker
    relay: EventRelay


def handler_map(handlers: Iterable[RunPurposeHandler[Any]]) -> Mapping[str, RunPurposeHandler[Any]]:
    result: dict[str, RunPurposeHandler[Any]] = {}
    for handler in handlers:
        purpose = RunPurpose(handler.purpose).value
        if purpose in result:
            raise ValueError(f"Duplicate run purpose handler: {purpose}")
        result[purpose] = handler
    return result


def build_execution_runtime(
    *,
    transaction: TransactionFactory[Any],
    publisher: EventPublisher,
    gateway: LlmGateway,
    context_provider: ContextProvider[Any],
    connections: AiConnectionQuery[Any],
    handlers: Iterable[RunPurposeHandler[Any]],
    config: ExecutorConfig | None = None,
    clock: Clock = utc_now,
) -> ExecutionRuntime:
    config = config or ExecutorConfig()
    store, hooks = SqlRunStore(), SqlAlchemyTransactionHooks()
    relay, wakeup, inflight = EventRelay(publisher), LoopSignal(), InFlightCalls()
    handlers_by_purpose = handler_map(handlers)
    announcer = RunAnnouncer(hooks, relay, clock, wakeup)
    finisher = RunFinisher(
        transaction=transaction,
        store=store,
        hooks=hooks,
        handlers=handlers_by_purpose,
        announcer=announcer,
        clock=clock,
    )
    recovery = RunRecovery(
        transaction=transaction, store=store, finisher=finisher, config=config, clock=clock
    )
    worker = RunWorker(
        WorkerDependencies(
            transaction=transaction,
            store=store,
            hooks=hooks,
            handlers=handlers_by_purpose,
            context_provider=context_provider,
            gateway=gateway,
            announcer=announcer,
            finisher=finisher,
            recovery=recovery,
            relay=relay,
            wakeup=wakeup,
            inflight=inflight,
            config=config,
            clock=clock,
        )
    )
    control = RunControlService(
        store=store,
        connections=connections,
        hooks=hooks,
        announcer=announcer,
        inflight=inflight,
        clock=clock,
    )
    return ExecutionRuntime(RunRegistrationService(store, connections, announcer), control, worker, relay)
