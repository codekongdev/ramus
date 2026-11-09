"""Bounded project fan-out for one API process and one asyncio event loop.

There is no event history: reconnecting clients refetch state. Multiple API processes need a shared
transport adapter. Synchronous transaction hooks reach this broker through the application's relay.
"""

import asyncio
from collections import defaultdict
from collections.abc import Callable
from uuid import UUID

from ramus_api.modules.realtime.application.ports import StreamClosed
from ramus_api.modules.realtime.application.schemas import validate_event
from ramus_api.modules.realtime.domain.events import ProjectEvent


class Subscription:
    def __init__(self, queue_size: int, remove: Callable[[], None]) -> None:
        self._queue: asyncio.Queue[ProjectEvent | None] = asyncio.Queue(maxsize=queue_size)
        self._remove = remove
        self._closed = False

    def offer(self, event: ProjectEvent) -> None:
        if self._closed:
            return
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            # Silently dropping a message would leave this client permanently out of sync.
            self.close()

    async def next(self, timeout: float) -> ProjectEvent | None:
        if self._closed:
            raise StreamClosed()
        try:
            event = await asyncio.wait_for(self._queue.get(), timeout)
        except TimeoutError:
            return None
        if event is None or self._closed:
            raise StreamClosed()
        return event

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        while not self._queue.empty():
            self._queue.get_nowait()
        self._queue.put_nowait(None)  # Wake a pending ``next`` call immediately.
        self._remove()


class InProcessEventBroker:
    def __init__(self, queue_size: int = 128) -> None:
        if queue_size < 1:
            raise ValueError("Subscriber queues must have positive capacity")
        self._queue_size = queue_size
        self._subscribers: dict[UUID, set[Subscription]] = defaultdict(set)

    @property
    def subscription_count(self) -> int:
        return sum(len(items) for items in self._subscribers.values())

    def subscribe(self, project_id: UUID) -> Subscription:
        def remove() -> None:
            subscribers = self._subscribers.get(project_id)
            if subscribers is not None:
                subscribers.discard(subscription)
                if not subscribers:
                    self._subscribers.pop(project_id, None)

        subscription = Subscription(self._queue_size, remove)
        self._subscribers[project_id].add(subscription)
        return subscription

    async def publish(self, event: ProjectEvent) -> None:
        valid = validate_event(event)
        for subscriber in tuple(self._subscribers.get(valid.project_id, ())):
            subscriber.offer(valid)

    def close(self) -> None:
        for subscribers in tuple(self._subscribers.values()):
            for subscription in tuple(subscribers):
                subscription.close()
