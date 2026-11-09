from typing import Protocol
from uuid import UUID

from ramus_api.modules.realtime.domain.events import ProjectEvent


class EventPublisher(Protocol):
    """Publish only after the transaction commits. Transport/replay is outside this port."""

    async def publish(self, event: ProjectEvent) -> None: ...


class StreamClosed(Exception):
    """The subscriber disconnected or fell behind; reconnecting clients must refetch state."""


class EventSubscription(Protocol):
    async def next(self, timeout: float) -> ProjectEvent | None:
        """Wait for an event; return None on timeout, or raise StreamClosed after closure."""

    def close(self) -> None: ...


class EventBroker(EventPublisher, Protocol):
    def subscribe(self, project_id: UUID) -> EventSubscription: ...

    def close(self) -> None: ...
