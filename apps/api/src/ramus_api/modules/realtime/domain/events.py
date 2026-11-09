from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID


class EventName(StrEnum):
    MEMBER_JOINED = "member.joined"
    CONVERSATION_CREATED = "conversation.created"
    MESSAGE_CREATED = "message.created"
    RUN_UPDATED = "run.updated"
    TASK_UPDATED = "task.updated"
    RESOURCE_UPDATED = "resource.updated"
    CONVERSATION_RESOURCES_UPDATED = "conversation_resources.updated"
    RESULT_UPDATED = "result.updated"
    CONVERSATION_INPUTS_UPDATED = "conversation_inputs.updated"


def freeze_data(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze_data(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze_data(item) for item in value)
    return value


@dataclass(frozen=True)
class ProjectEvent:
    """Project routing is internal; ``data`` contains the contract's SSE payload fields."""

    project_id: UUID
    name: EventName
    occurred_at: datetime
    data: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", EventName(self.name))
        object.__setattr__(self, "data", freeze_data(self.data))
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("Event time must be timezone-aware")
