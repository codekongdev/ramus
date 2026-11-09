from uuid import UUID

from ramus_api.modules.realtime.application.schemas import validate_event
from ramus_api.modules.realtime.domain.events import ProjectEvent


class FakeEventPublisher:
    """Collect validated events in publication order; no SSE transport or replay is simulated."""

    def __init__(self) -> None:
        self._events: list[ProjectEvent] = []

    @property
    def events(self) -> tuple[ProjectEvent, ...]:
        return tuple(self._events)

    def for_project(self, project_id: UUID) -> tuple[ProjectEvent, ...]:
        return tuple(event for event in self._events if event.project_id == project_id)

    async def publish(self, event: ProjectEvent) -> None:
        self._events.append(validate_event(event))
