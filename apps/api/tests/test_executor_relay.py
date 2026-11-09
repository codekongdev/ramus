"""Thread-to-loop hand-off used by commit hooks: ordering, failure isolation, wake-ups, aborts."""

import asyncio
import threading
from datetime import UTC, datetime
from uuid import UUID

import pytest

from ramus_api.modules.execution.application.inflight import InFlightCalls
from ramus_api.modules.execution.application.relay import EventRelay, LoopSignal
from ramus_api.modules.realtime.domain.events import EventName, ProjectEvent
from ramus_api.modules.realtime.fakes.publisher import FakeEventPublisher

NOW = datetime(2026, 11, 9, tzinfo=UTC)


def event(n: int) -> ProjectEvent:
    return ProjectEvent(
        UUID(int=1), EventName.CONVERSATION_RESOURCES_UPDATED, NOW, {"conversation_id": UUID(int=n)}
    )


class FlakyPublisher(FakeEventPublisher):
    async def publish(self, event: ProjectEvent) -> None:
        if event.data["conversation_id"] == UUID(int=2):
            raise ConnectionError("transport down")
        await super().publish(event)


async def test_events_enqueued_from_threads_are_published_in_order() -> None:
    publisher = FakeEventPublisher()
    relay = EventRelay(publisher)
    worker = threading.Thread(target=lambda: [relay.enqueue(event(n)) for n in range(1, 6)])
    worker.start()
    worker.join()
    assert await relay.flush() == 5
    assert [item.data["conversation_id"].int for item in publisher.events] == [1, 2, 3, 4, 5]
    assert await relay.flush() == 0


async def test_a_failed_publication_is_logged_and_later_events_still_go_out(caplog) -> None:
    publisher = FlakyPublisher()
    relay = EventRelay(publisher)
    for n in (1, 2, 3):
        relay.enqueue(event(n))
    assert await relay.flush() == 3
    assert [item.data["conversation_id"].int for item in publisher.events] == [1, 3]
    assert "ConnectionError" in caplog.text
    assert "transport down" not in caplog.text


async def test_relay_loop_publishes_events_enqueued_from_another_thread() -> None:
    publisher = FakeEventPublisher()
    relay = EventRelay(publisher)
    pump = asyncio.create_task(relay.run_forever(idle_timeout=30))
    await asyncio.sleep(0)
    await asyncio.to_thread(relay.enqueue, event(7))
    async with asyncio.timeout(5):
        while not publisher.events:
            await asyncio.sleep(0.01)
    pump.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pump
    assert publisher.events[0].data["conversation_id"] == UUID(int=7)


async def test_signal_keeps_a_notification_sent_before_binding_and_times_out_otherwise() -> None:
    signal = LoopSignal()
    with pytest.raises(RuntimeError):
        await signal.wait(0.01)
    signal.notify()
    signal.bind()
    assert await signal.wait(5) is True
    assert await signal.wait(0.01) is False
    await asyncio.to_thread(signal.notify)
    assert await signal.wait(5) is True


async def test_abort_cancels_only_the_registered_call_from_another_thread() -> None:
    calls = InFlightCalls()
    gate = asyncio.Event()
    call = asyncio.ensure_future(gate.wait())
    calls.register(UUID(int=1), call)
    assert await asyncio.to_thread(calls.abort, UUID(int=2)) is False
    assert await asyncio.to_thread(calls.abort, UUID(int=1)) is True
    with pytest.raises(asyncio.CancelledError):
        await call
    calls.unregister(UUID(int=1), call)
    assert calls.abort(UUID(int=1)) is False
