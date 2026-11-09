"""B3: the AI input context for one conversation (contracts.md §6 ``ContextProvider``).

The pure part turns pinned resource revisions and received conclusion snapshots into the
execution module's ``ConversationContext``. Order is deterministic so the same pins always
produce the same model input. Nothing here resolves to a resource's or result's *latest* version.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.execution.domain.models import ConversationContext, ResourceInput, ResultInput
from ramus_api.modules.resources.domain.models import ResourceKind

TransactionT = TypeVar("TransactionT")
SessionT = TypeVar("SessionT", contravariant=True)


@dataclass(frozen=True)
class PinnedRevision:
    """A revision a conversation pinned, with the content the model will read."""

    resource_id: UUID
    revision_id: UUID
    kind: ResourceKind
    name: str
    instructions: str | None
    content: str | None


@dataclass(frozen=True)
class ReceivedConclusion:
    """A conclusion linked to a conversation as input (share or new conversation), as snapshotted."""

    result_id: UUID
    result_revision_id: UUID
    version: int
    title: str
    conclusion: str


def resource_inputs(pins: Iterable[PinnedRevision]) -> tuple[ResourceInput, ...]:
    ordered = sorted(pins, key=lambda p: (p.name.casefold(), str(p.resource_id)))
    return tuple(
        ResourceInput(
            resource_id=p.resource_id,
            revision_id=p.revision_id,
            kind=p.kind.value,
            name=p.name,
            instructions=p.instructions,
            content=p.content,
        )
        for p in ordered
    )


def result_inputs(conclusions: Iterable[ReceivedConclusion]) -> tuple[ResultInput, ...]:
    ordered = sorted(conclusions, key=lambda c: (c.title.casefold(), str(c.result_id)))
    return tuple(
        ResultInput(
            result_id=c.result_id,
            result_revision_id=c.result_revision_id,
            version=c.version,
            title=c.title,
            conclusion=c.conclusion,
        )
        for c in ordered
    )


def build_context(
    pins: Iterable[PinnedRevision], conclusions: Iterable[ReceivedConclusion]
) -> ConversationContext:
    return ConversationContext(resources=resource_inputs(pins), results=result_inputs(conclusions))


# --- sources the provider reads from (structural; implemented in resources and sharing) ---------


class PinnedRevisionSource(Protocol[SessionT]):
    def pinned(self, session: SessionT, conversation_id: UUID) -> Sequence[PinnedRevision]: ...

    def copy_pins(
        self, session: SessionT, source_conversation_id: UUID, target_conversation_id: UUID
    ) -> None:
        """Makes the target pin exactly the source's revision ids, replacing whatever it had."""
        ...


class ReceivedConclusionSource(Protocol[SessionT]):
    def received(self, session: SessionT, conversation_id: UUID) -> Sequence[ReceivedConclusion]: ...


@dataclass(frozen=True)
class PinnedContextProvider(Generic[TransactionT]):
    """Implements execution's ``ContextProvider`` for track B. Runs in the caller's transaction."""

    resources: PinnedRevisionSource[TransactionT]
    conclusions: ReceivedConclusionSource[TransactionT]

    def snapshot(self, session: TransactionT, conversation_id: UUID) -> ConversationContext:
        return build_context(
            self.resources.pinned(session, conversation_id),
            self.conclusions.received(session, conversation_id),
        )

    def copy_resources(
        self, session: TransactionT, source_conversation_id: UUID, target_conversation_id: UUID
    ) -> None:
        """Branch inheritance (F-09, AC-15): the child starts with the parent's exact revisions.

        Received conclusions are not copied; the child gets only what is shared to it later.
        """
        if source_conversation_id == target_conversation_id:
            raise ValueError("A conversation cannot inherit from itself")
        self.resources.copy_pins(session, source_conversation_id, target_conversation_id)
