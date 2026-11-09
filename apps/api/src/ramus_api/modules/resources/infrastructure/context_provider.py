"""Factory for track B's ``ContextProvider`` (contracts.md §6). The executor (track A) wires it in."""

from sqlalchemy.orm import Session

from ramus_api.modules.resources.application.context import PinnedContextProvider
from ramus_api.modules.resources.infrastructure.pinned_source import SqlPinnedRevisionSource
from ramus_api.modules.sharing.infrastructure.received_source import SqlReceivedConclusionSource


def build_context_provider() -> PinnedContextProvider[Session]:
    return PinnedContextProvider(
        resources=SqlPinnedRevisionSource(), conclusions=SqlReceivedConclusionSource()
    )
