"""Bounded SSE fan-out and real ASGI streaming; PostgreSQL tests use only temporary databases."""

import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.requests import ClientDisconnect

from ramus_api.main import create_app
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.realtime.application.ports import StreamClosed
from ramus_api.modules.realtime.domain.events import EventName, ProjectEvent
from ramus_api.modules.realtime.infrastructure.broker import InProcessEventBroker
from ramus_api.modules.realtime.presentation.routes import EventStreamResponse
from ramus_api.modules.realtime.presentation.stream import stream_events
from ramus_api.settings import Settings
from ramus_api.shared.domain import BusinessError

PROJECT, OTHER_PROJECT, CONVERSATION, MESSAGE = (UUID(int=value) for value in range(1, 5))


def message_event(project_id: UUID = PROJECT, seq: int = 1) -> ProjectEvent:
    return ProjectEvent(
        project_id,
        EventName.MESSAGE_CREATED,
        datetime.now(UTC),
        {"conversation_id": CONVERSATION, "message_id": MESSAGE, "seq": seq},
    )


async def allow() -> None:
    pass


async def test_broker_fans_out_only_to_current_project_subscribers_without_replay() -> None:
    broker = InProcessEventBroker()
    await broker.publish(message_event())
    first, second = broker.subscribe(PROJECT), broker.subscribe(PROJECT)
    other = broker.subscribe(OTHER_PROJECT)
    assert await first.next(0.001) is None  # No stored history, including before first subscription.
    await broker.publish(message_event(seq=2))
    assert (await first.next(0.1)).data["seq"] == 2
    assert (await second.next(0.1)).data["seq"] == 2
    assert await other.next(0.001) is None
    first.close()
    assert broker.subscription_count == 2
    broker.close()
    assert broker.subscription_count == 0


async def test_invalid_payload_never_reaches_a_subscriber_or_leaks_secrets() -> None:
    broker = InProcessEventBroker()
    subscription = broker.subscribe(PROJECT)
    event = message_event()
    invalid = ProjectEvent(event.project_id, event.name, event.occurred_at, {**event.data, "body": "private"})
    with pytest.raises(ValueError) as caught:
        await broker.publish(invalid)
    assert "private" not in str(caught.value)
    assert await subscription.next(0.001) is None
    broker.close()


async def test_slow_subscriber_is_closed_instead_of_silently_missing_events() -> None:
    broker = InProcessEventBroker(queue_size=1)
    slow, fast = broker.subscribe(PROJECT), broker.subscribe(PROJECT)
    await broker.publish(message_event())
    assert (await fast.next(0.1)).data["seq"] == 1
    await broker.publish(message_event(seq=2))
    with pytest.raises(StreamClosed):
        await slow.next(0.1)
    assert (await fast.next(0.1)).data["seq"] == 2
    assert broker.subscription_count == 1
    broker.close()


async def test_close_wakes_waiters_and_is_idempotent() -> None:
    broker = InProcessEventBroker()
    subscription = broker.subscribe(PROJECT)
    waiting = asyncio.create_task(subscription.next(60))
    await asyncio.sleep(0)
    subscription.close()
    subscription.close()
    with pytest.raises(StreamClosed):
        await asyncio.wait_for(waiting, 0.1)
    assert broker.subscription_count == 0


async def test_stream_frames_metadata_then_heartbeats_and_cleans_up() -> None:
    broker = InProcessEventBroker()
    subscription = broker.subscribe(PROJECT)
    checks = []

    async def authorize() -> None:
        checks.append(True)

    stream = stream_events(subscription, authorize, heartbeat_seconds=0.01)
    assert await anext(stream) == ": ping\n\n"
    await broker.publish(message_event())
    frame = await anext(stream)
    assert frame.startswith("event: message.created\ndata: ")
    payload = json.loads(frame.split("data: ", 1)[1])
    assert set(payload) == {"conversation_id", "message_id", "seq", "occurred_at"}
    assert "id:" not in frame  # The contract does not use event IDs or replay.
    assert await asyncio.wait_for(anext(stream), 0.2) == ": ping\n\n"
    assert checks == [True]
    await stream.aclose()
    assert broker.subscription_count == 0


async def test_reauthorization_failure_ends_stream_and_releases_subscription() -> None:
    broker = InProcessEventBroker()

    async def deny() -> None:
        raise BusinessError("UNAUTHORIZED", "로그인이 필요합니다.", 401)

    stream = stream_events(broker.subscribe(PROJECT), deny, heartbeat_seconds=0.001)
    await anext(stream)
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(stream), 0.1)
    assert broker.subscription_count == 0


async def test_stream_cancellation_releases_subscription() -> None:
    broker = InProcessEventBroker()
    stream = stream_events(broker.subscribe(PROJECT), allow)
    await anext(stream)
    pending = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert broker.subscription_count == 0


async def test_response_header_disconnect_closes_subscription_before_iteration() -> None:
    broker = InProcessEventBroker()
    subscription = broker.subscribe(PROJECT)
    response = EventStreamResponse(stream_events(subscription, allow), close=subscription.close)

    async def send(_message) -> None:
        raise OSError("connection closed")

    async def receive():
        return {"type": "http.disconnect"}

    with pytest.raises(ClientDisconnect):
        await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
    assert broker.subscription_count == 0


def test_anonymous_stream_is_401_without_database_access(unit_settings: Settings) -> None:
    with TestClient(create_app(unit_settings)) as client:
        response = client.get(f"/api/projects/{PROJECT}/events")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def signed_in_client(app, mailer):
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://testserver")
    email = f"stream-{uuid4().hex}@example.test"
    result = await client.post(
        "/api/auth/email-code", json={"email": email}, headers={"Idempotency-Key": f"code-{uuid4()}"}
    )
    assert result.status_code == 202
    code = next(item.code for item in reversed(mailer.deliveries) if item.email == email)
    verified = await client.post(
        "/api/auth/verify", json={"email": email, "code": code},
        headers={"Idempotency-Key": f"verify-{uuid4()}"},
    )
    assert verified.status_code == 200
    return client, verified.json()


@pytest.mark.integration
async def test_stream_hides_nonmember_projects(integration_settings: Settings) -> None:
    mailer = FakeMailer()
    app = create_app(integration_settings, mailer=mailer)
    client, _ = await signed_in_client(app, mailer)
    try:
        response = await client.get(f"/api/projects/{uuid4()}/events")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
        assert app.state.container.events.subscription_count == 0
    finally:
        await client.aclose()
        app.state.container.database.dispose()


@pytest.mark.integration
async def test_authorized_asgi_stream_sends_chunks_ignores_last_event_id_and_disconnects(
    integration_settings: Settings,
) -> None:
    mailer = FakeMailer()
    app = create_app(integration_settings, mailer=mailer)
    client, profile = await signed_in_client(app, mailer)
    project = UUID(profile["default_project_id"])
    broker = app.state.container.events
    await broker.publish(message_event(project, 1))  # Previous events must not be replayed.
    path = f"/api/projects/{project}/events"
    messages, incoming = [], asyncio.Queue()
    connected, received = asyncio.Event(), asyncio.Event()

    async def receive():
        return await incoming.get()

    async def send(message):
        messages.append(message)
        if message["type"] == "http.response.body":
            if message.get("body") == b": ping\n\n":
                connected.set()
            elif b"event: message.created" in message.get("body", b""):
                received.set()

    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1", "method": "GET", "scheme": "http", "path": path,
        "raw_path": path.encode(), "query_string": b"", "root_path": "",
        "headers": [(b"cookie", f"ramus_session={client.cookies['ramus_session']}".encode()),
                    (b"last-event-id", b"old-id")],
        "client": ("127.0.0.1", 12345), "server": ("testserver", 80),
    }
    task = asyncio.create_task(app(scope, receive, send))
    try:
        await asyncio.wait_for(connected.wait(), 2)
        assert broker.subscription_count == 1
        await broker.publish(message_event(project, 2))
        await asyncio.wait_for(received.wait(), 2)
        await incoming.put({"type": "http.disconnect"})
        await asyncio.wait_for(task, 2)
        start = next(item for item in messages if item["type"] == "http.response.start")
        assert start["status"] == 200
        headers = dict(start["headers"])
        assert headers[b"content-type"].startswith(b"text/event-stream")
        assert headers[b"cache-control"] == b"no-cache"
        assert headers[b"x-accel-buffering"] == b"no"
        frames = [item["body"] for item in messages if item["type"] == "http.response.body"]
        assert len(frames) == 2
        payload = json.loads(frames[1].split(b"data: ", 1)[1])
        assert payload["seq"] == 2
        assert broker.subscription_count == 0
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await client.aclose()
        broker.close()
        app.state.container.database.dispose()
