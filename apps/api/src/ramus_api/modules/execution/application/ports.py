"""Public contracts from contracts.md §6. Transactions are owned by the caller."""

from collections.abc import Mapping
from typing import Any, Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.execution.domain.models import (
    ConversationContext,
    LlmRequest,
    RunError,
    RunRef,
    RunRequest,
    RunView,
)

TransactionT = TypeVar("TransactionT", contravariant=True)


class ContextProvider(Protocol[TransactionT]):
    def snapshot(self, session: TransactionT, conversation_id: UUID) -> ConversationContext: ...

    def copy_resources(
        self, session: TransactionT, source_conversation_id: UUID, target_conversation_id: UUID
    ) -> None: ...


class RunRequester(Protocol[TransactionT]):
    """Raise AI_CONNECTION_REQUIRED or ACTIVE_RUN_EXISTS before accepting a run."""

    def request(self, session: TransactionT, request: RunRequest) -> RunRef: ...


class RunPurposeHandler(Protocol[TransactionT]):
    purpose: str

    def build_request(
        self, session: TransactionT, run: RunView, context: ConversationContext
    ) -> LlmRequest: ...

    def complete(self, session: TransactionT, run: RunView, output: Mapping[str, Any]) -> None: ...

    def fail(self, session: TransactionT, run: RunView, error: RunError) -> None: ...


class LlmGateway(Protocol):
    """Called outside the DB transaction. Output is schema-validated and immutable."""

    async def complete(self, request: LlmRequest) -> Mapping[str, Any]: ...


# The roadmap uses LLMGateway; the frozen contract spells it LlmGateway.
LLMGateway = LlmGateway
