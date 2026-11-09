"""SSE framing and heartbeat lifecycle. The response owns and closes its subscription."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from ramus_api.modules.realtime.application.ports import EventSubscription, StreamClosed
from ramus_api.modules.realtime.application.schemas import event_json_data
from ramus_api.shared.domain import BusinessError

HEARTBEAT_SECONDS = 15.0


async def stream_events(
    subscription: EventSubscription,
    authorize: Callable[[], Awaitable[None]],
    heartbeat_seconds: float = HEARTBEAT_SECONDS,
) -> AsyncIterator[str]:
    if heartbeat_seconds <= 0:
        raise ValueError("Heartbeat interval must be positive")
    loop = asyncio.get_running_loop()
    heartbeat_at = loop.time() + heartbeat_seconds
    try:
        # Flush the response immediately even when this project has no activity.
        yield ": ping\n\n"
        while True:
            remaining = heartbeat_at - loop.time()
            if remaining <= 0:
                try:
                    await authorize()
                except BusinessError:
                    return  # Session expiry or membership removal ends the old authorized stream.
                yield ": ping\n\n"
                heartbeat_at = loop.time() + heartbeat_seconds
                continue
            try:
                event = await subscription.next(remaining)
            except StreamClosed:
                return
            if event is not None:
                yield f"event: {event.name.value}\ndata: {event_json_data(event)}\n\n"
    finally:
        subscription.close()
