"""Thread-safe hand-off from synchronous commit hooks to the asynchronous executor loop.

``RunRequester.request`` and the cancel/retry services are synchronous and may run in FastAPI's
thread pool, while ``EventPublisher.publish`` is a coroutine. Commit hooks therefore only enqueue
here; a coroutine on the executor's loop drains the queue in order.
"""

import asyncio
import logging
import threading
from collections import deque

from ramus_api.modules.realtime.application.ports import EventPublisher
from ramus_api.modules.realtime.domain.events import ProjectEvent

logger = logging.getLogger(__name__)


class LoopSignal:
    """Wakes coroutines on one event loop from any thread. Notifications before ``bind`` are kept."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._event: asyncio.Event | None = None
        self._pending = False

    def bind(self) -> None:
        """Attaches the signal to the running loop. Call from inside that loop."""
        loop, event = asyncio.get_running_loop(), asyncio.Event()
        with self._lock:
            self._loop, self._event = loop, event
            if self._pending:
                event.set()
            self._pending = False

    def notify(self) -> None:
        with self._lock:
            loop, event = self._loop, self._event
            if loop is None or event is None:
                self._pending = True
                return
        try:
            loop.call_soon_threadsafe(event.set)
        except RuntimeError:
            logger.warning("Executor signal dropped because its event loop is closed")

    async def wait(self, timeout: float) -> bool:
        """True when notified before ``timeout`` seconds passed."""
        event = self._event
        if event is None:
            raise RuntimeError("LoopSignal.wait called before bind")
        try:
            await asyncio.wait_for(event.wait(), timeout)
            return True
        except TimeoutError:
            return False
        finally:
            event.clear()


class EventRelay:
    """FIFO of committed events. Publication failures are logged and do not block later events."""

    def __init__(self, publisher: EventPublisher) -> None:
        self._publisher = publisher
        self._lock = threading.Lock()
        self._queue: deque[ProjectEvent] = deque()
        self._signal = LoopSignal()
        self._publishing = asyncio.Lock()

    def enqueue(self, event: ProjectEvent) -> None:
        with self._lock:
            self._queue.append(event)
        self._signal.notify()

    def _next(self) -> ProjectEvent | None:
        with self._lock:
            return self._queue.popleft() if self._queue else None

    async def flush(self) -> int:
        """Publishes every queued event in order and returns how many were attempted."""
        count = 0
        async with self._publishing:
            while (event := self._next()) is not None:
                count += 1
                try:
                    await self._publisher.publish(event)
                except Exception as error:  # noqa: BLE001 - a lost SSE event is recovered by refetch
                    logger.warning(
                        "Run event publication failed: event=%s error=%s", event.name, type(error).__name__
                    )
        return count

    async def run_forever(self, idle_timeout: float) -> None:
        self._signal.bind()
        while True:
            await self.flush()
            await self._signal.wait(idle_timeout)
