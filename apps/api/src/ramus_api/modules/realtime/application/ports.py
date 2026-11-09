from typing import Protocol

from ramus_api.modules.realtime.domain.events import ProjectEvent


class EventPublisher(Protocol):
    """Publish only after the transaction commits. Transport/replay is outside this port."""

    async def publish(self, event: ProjectEvent) -> None: ...
