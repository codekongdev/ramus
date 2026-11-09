"""A5 wiring. A2 supplies its writer; B3 supplies ContextProvider, and A3 the gateway/connections."""

from collections.abc import Iterable
from typing import Any

from ramus_api.modules.conversations.application.ports import ConversationWriter
from ramus_api.modules.conversations.application.work_inputs import WorkInputReader
from ramus_api.modules.conversations.infrastructure.work_inputs import SqlWorkInputReader
from ramus_api.modules.execution.application.config import Clock, ExecutorConfig
from ramus_api.modules.execution.application.ports import (
    AiConnectionQuery,
    ContextProvider,
    LlmGateway,
    RunPurposeHandler,
)
from ramus_api.modules.execution.application.runtime_ports import TransactionFactory
from ramus_api.modules.execution.application.work import WorkPurposeHandler
from ramus_api.modules.execution.composition import ExecutionRuntime, build_execution_runtime
from ramus_api.modules.execution.infrastructure.branch_tasks import SqlBranchTaskStore
from ramus_api.modules.realtime.application.ports import EventPublisher
from ramus_api.modules.results.infrastructure.task_results import SqlTaskResultQuery
from ramus_api.shared.domain.primitives import utc_now


def build_work_execution_runtime(
    *,
    transaction: TransactionFactory[Any],
    publisher: EventPublisher,
    gateway: LlmGateway,
    context_provider: ContextProvider[Any],
    connections: AiConnectionQuery[Any],
    writer: ConversationWriter[Any],
    inputs: WorkInputReader[Any] | None = None,
    handlers: Iterable[RunPurposeHandler[Any]] = (),
    config: ExecutorConfig | None = None,
    clock: Clock = utc_now,
) -> ExecutionRuntime:
    tasks = SqlBranchTaskStore(SqlTaskResultQuery())
    return build_execution_runtime(
        transaction=transaction,
        publisher=publisher,
        gateway=gateway,
        context_provider=context_provider,
        connections=connections,
        handlers=handlers,
        handler_factory=lambda requester: (
            WorkPurposeHandler(
                inputs=inputs if inputs is not None else SqlWorkInputReader(),
                writer=writer,
                tasks=tasks,
                contexts=context_provider,
                requester=requester,
            ),
        ),
        task_lifecycle=tasks,
        config=config,
        clock=clock,
    )
