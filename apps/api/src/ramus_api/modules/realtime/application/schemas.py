"""Allowlisted SSE payload DTOs. No user body or credential field is accepted."""

import json
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError

from ramus_api.modules.execution.domain.models import RunPurpose, RunStatus, TaskStatus
from ramus_api.modules.realtime.domain.events import EventName, ProjectEvent
from ramus_api.modules.results.domain.models import ResultDraftStatus

PositiveInt = Annotated[int, Field(strict=True, gt=0)]
ShortText = Annotated[str, Field(min_length=1, max_length=100)]


class EventDto(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AccountPayload(EventDto):
    id: UUID
    display_name: ShortText


class ConversationPayload(EventDto):
    id: UUID
    project_id: UUID
    parent_id: UUID | None
    task_id: UUID | None
    title: ShortText
    path: list[ShortText]
    created_by: UUID
    created_at: AwareDatetime


class RunPayload(EventDto):
    id: UUID
    purpose: RunPurpose
    status: RunStatus
    task_id: UUID | None
    requested_by: UUID


class TaskPayload(EventDto):
    id: UUID
    title: ShortText
    status: TaskStatus
    child_conversation_id: UUID
    result_id: UUID | None


class MemberJoined(EventDto):
    occurred_at: AwareDatetime
    project_id: UUID
    account: AccountPayload


class ConversationCreated(EventDto):
    occurred_at: AwareDatetime
    project_id: UUID
    conversation: ConversationPayload


class MessageCreated(EventDto):
    occurred_at: AwareDatetime
    conversation_id: UUID
    message_id: UUID
    seq: PositiveInt


class RunUpdated(EventDto):
    occurred_at: AwareDatetime
    conversation_id: UUID
    run: RunPayload


class TaskUpdated(EventDto):
    occurred_at: AwareDatetime
    source_conversation_id: UUID
    task: TaskPayload


class ResourceUpdated(EventDto):
    occurred_at: AwareDatetime
    project_id: UUID
    resource_id: UUID
    latest_revision_id: UUID
    latest_number: PositiveInt


class ConversationResourcesUpdated(EventDto):
    occurred_at: AwareDatetime
    conversation_id: UUID


class ResultUpdated(EventDto):
    occurred_at: AwareDatetime
    result_id: UUID
    task_id: UUID
    draft_status: ResultDraftStatus | None
    latest_version: PositiveInt | None


class ConversationInputsUpdated(EventDto):
    occurred_at: AwareDatetime
    conversation_id: UUID


EVENT_SCHEMAS: dict[EventName, type[EventDto]] = {
    EventName.MEMBER_JOINED: MemberJoined,
    EventName.CONVERSATION_CREATED: ConversationCreated,
    EventName.MESSAGE_CREATED: MessageCreated,
    EventName.RUN_UPDATED: RunUpdated,
    EventName.TASK_UPDATED: TaskUpdated,
    EventName.RESOURCE_UPDATED: ResourceUpdated,
    EventName.CONVERSATION_RESOURCES_UPDATED: ConversationResourcesUpdated,
    EventName.RESULT_UPDATED: ResultUpdated,
    EventName.CONVERSATION_INPUTS_UPDATED: ConversationInputsUpdated,
}


def _json_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat() if value.tzinfo is not None else value.isoformat()
    if hasattr(value, "items"):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def validate_event(event: ProjectEvent) -> ProjectEvent:
    """Recheck at publication so directly constructed events cannot bypass the allowlist."""
    try:
        if "occurred_at" in event.data:
            raise ValueError("Reserved event field")
        raw = json.dumps(_json_value({**event.data, "occurred_at": event.occurred_at}))
        dto = EVENT_SCHEMAS[event.name].model_validate_json(raw)
        if hasattr(dto, "project_id") and dto.project_id != event.project_id:
            raise ValueError("Project mismatch")
        if isinstance(dto, ConversationCreated) and dto.conversation.project_id != event.project_id:
            raise ValueError("Project mismatch")
        if dto.occurred_at.tzinfo is None:
            raise ValueError("Missing timezone")
    except (KeyError, TypeError, ValueError, ValidationError):
        raise ValueError("실시간 이벤트 형식이 올바르지 않습니다.") from None
    data = dto.model_dump(exclude={"occurred_at"})
    return ProjectEvent(event.project_id, event.name, dto.occurred_at.astimezone(UTC), data)


def event_json_data(event: ProjectEvent) -> str:
    """Serialize just SSE data; event name/project routing are handled by the transport."""
    valid = validate_event(event)
    return json.dumps(
        _json_value({**valid.data, "occurred_at": valid.occurred_at}), ensure_ascii=False, allow_nan=False
    )
