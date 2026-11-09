from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class InputOrigin(StrEnum):
    SHARE = "share"
    NEW_CONVERSATION = "new_conversation"


@dataclass(frozen=True)
class ResultUsage:
    source_conversation_id: UUID
    target_conversation_id: UUID
    result_id: UUID
