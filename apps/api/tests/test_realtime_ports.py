import json
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from ramus_api.modules.realtime.application.ports import EventPublisher
from ramus_api.modules.realtime.application.schemas import EVENT_SCHEMAS, event_json_data, validate_event
from ramus_api.modules.realtime.domain.events import EventName, ProjectEvent
from ramus_api.modules.realtime.fakes.publisher import FakeEventPublisher

PROJECT, CONVERSATION, ACCOUNT, MESSAGE, RUN, TASK, RESULT = (UUID(int=n) for n in range(1, 8))
NOW = datetime(2026, 11, 9, 4, 0, tzinfo=UTC)


def valid_payloads():
    return {
        EventName.MEMBER_JOINED: {
            "project_id": PROJECT,
            "account": {"id": ACCOUNT, "display_name": "테스터"},
        },
        EventName.CONVERSATION_CREATED: {
            "project_id": PROJECT,
            "conversation": {
                "id": CONVERSATION,
                "project_id": PROJECT,
                "parent_id": None,
                "task_id": None,
                "title": "대화",
                "path": [],
                "created_by": ACCOUNT,
                "created_at": NOW,
            },
        },
        EventName.MESSAGE_CREATED: {"conversation_id": CONVERSATION, "message_id": MESSAGE, "seq": 1},
        EventName.RUN_UPDATED: {
            "conversation_id": CONVERSATION,
            "run": {
                "id": RUN,
                "purpose": "work",
                "status": "pending",
                "task_id": None,
                "requested_by": ACCOUNT,
            },
        },
        EventName.TASK_UPDATED: {
            "source_conversation_id": CONVERSATION,
            "task": {
                "id": TASK,
                "title": "작업",
                "status": "ready",
                "child_conversation_id": UUID(int=20),
                "result_id": None,
            },
        },
        EventName.RESOURCE_UPDATED: {
            "project_id": PROJECT,
            "resource_id": UUID(int=21),
            "latest_revision_id": UUID(int=22),
            "latest_number": 1,
        },
        EventName.CONVERSATION_RESOURCES_UPDATED: {"conversation_id": CONVERSATION},
        EventName.RESULT_UPDATED: {
            "result_id": RESULT,
            "task_id": TASK,
            "draft_status": "ready",
            "latest_version": None,
        },
        EventName.CONVERSATION_INPUTS_UPDATED: {"conversation_id": CONVERSATION},
    }


@pytest.mark.parametrize("name", list(EventName))
async def test_all_contract_events_validate_and_publish_without_bodies(name) -> None:
    publisher: EventPublisher = FakeEventPublisher()
    await publisher.publish(ProjectEvent(PROJECT, name, NOW, valid_payloads()[name]))
    assert len(publisher.events) == 1
    payload = json.loads(event_json_data(publisher.events[0]))
    assert datetime.fromisoformat(payload.pop("occurred_at")) == NOW
    assert set(payload) == set(valid_payloads()[name])
    assert publisher.for_project(UUID(int=99)) == ()
    assert publisher.for_project(PROJECT) == publisher.events


def test_event_catalog_matches_the_frozen_contract_not_roadmap_draft() -> None:
    assert set(EVENT_SCHEMAS) == set(EventName)
    assert len(EventName) == 9
    assert "share.created" not in EventName
    assert "conversation_inputs.updated" in EventName


@pytest.mark.parametrize("field", ["body", "conclusion", "api_key", "ciphertext", "credential_account_id"])
async def test_publisher_rejects_additional_fields_without_recording_or_leaking(field) -> None:
    fake = FakeEventPublisher()
    payload = {**valid_payloads()[EventName.MESSAGE_CREATED], field: "fixture-secret"}
    with pytest.raises(ValueError) as caught:
        await fake.publish(ProjectEvent(PROJECT, EventName.MESSAGE_CREATED, NOW, payload))
    assert "fixture-secret" not in str(caught.value)
    assert fake.events == ()


async def test_nested_unknown_fields_and_incorrect_types_are_rejected() -> None:
    invalid = [
        {"conversation_id": CONVERSATION, "message_id": MESSAGE, "seq": True},
        {"conversation_id": "not-a-uuid", "message_id": MESSAGE, "seq": 1},
        {"conversation_id": CONVERSATION, "message_id": MESSAGE, "seq": "1"},
        {"conversation_id": CONVERSATION, "message_id": MESSAGE, "seq": 0},
        {"conversation_id": CONVERSATION, "message_id": MESSAGE},
    ]
    for payload in invalid:
        with pytest.raises(ValueError):
            validate_event(ProjectEvent(PROJECT, EventName.MESSAGE_CREATED, NOW, payload))
    payload = valid_payloads()[EventName.RUN_UPDATED]
    for changes in ({"status": "ready"}, {"api_key": "fixture-secret"}):
        changed = {**payload, "run": {**payload["run"], **changes}}
        with pytest.raises(ValueError):
            validate_event(ProjectEvent(PROJECT, EventName.RUN_UPDATED, NOW, changed))


async def test_published_payloads_are_deeply_immutable_and_do_not_follow_input_mutations() -> None:
    payload = valid_payloads()[EventName.CONVERSATION_CREATED]
    event = ProjectEvent(PROJECT, EventName.CONVERSATION_CREATED, NOW, payload)
    payload["conversation"]["title"] = "뒤늦은 변경"
    publisher = FakeEventPublisher()
    await publisher.publish(event)
    assert publisher.events[0].data["conversation"]["title"] == "대화"
    with pytest.raises(TypeError):
        publisher.events[0].data["conversation"]["title"] = "변경"


@pytest.mark.parametrize("naive", [datetime(2026, 11, 9), "2026-11-09T04:00:00"])
def test_nested_conversation_created_at_requires_a_timezone(naive) -> None:
    payload = valid_payloads()[EventName.CONVERSATION_CREATED]
    payload["conversation"]["created_at"] = naive
    with pytest.raises(ValueError):
        event_json_data(ProjectEvent(PROJECT, EventName.CONVERSATION_CREATED, NOW, payload))


def test_all_event_timestamps_are_normalized_to_utc() -> None:
    seoul = timezone(timedelta(hours=9))
    payload = valid_payloads()[EventName.CONVERSATION_CREATED]
    payload["conversation"]["created_at"] = "2026-11-09T13:00:00+09:00"
    event = ProjectEvent(PROJECT, EventName.CONVERSATION_CREATED, NOW.astimezone(seoul), payload)
    data = json.loads(event_json_data(event))
    assert data["occurred_at"] == "2026-11-09T04:00:00+00:00"
    assert data["conversation"]["created_at"] == "2026-11-09T04:00:00+00:00"


def test_project_routing_timezones_and_reserved_fields_are_checked() -> None:
    payload = valid_payloads()[EventName.MEMBER_JOINED]
    with pytest.raises(ValueError):
        validate_event(ProjectEvent(UUID(int=99), EventName.MEMBER_JOINED, NOW, payload))
    conversation = valid_payloads()[EventName.CONVERSATION_CREATED]
    conversation["conversation"]["project_id"] = UUID(int=99)
    with pytest.raises(ValueError):
        validate_event(ProjectEvent(PROJECT, EventName.CONVERSATION_CREATED, NOW, conversation))
    with pytest.raises(ValueError):
        ProjectEvent(PROJECT, EventName.MEMBER_JOINED, NOW.replace(tzinfo=None), payload)
    with pytest.raises(ValueError):
        validate_event(ProjectEvent(PROJECT, EventName.MEMBER_JOINED, NOW, {**payload, "occurred_at": NOW}))
