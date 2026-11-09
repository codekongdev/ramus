from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class ConversationOrigin(StrEnum):
    TOP = "top"
    BRANCH = "branch"
    FROM_RESULT = "from_result"


class AuthorKind(StrEnum):
    HUMAN = "human"
    AI = "ai"
    SYSTEM = "system"


@dataclass(frozen=True)
class NewMessage:
    conversation_id: UUID
    author_kind: AuthorKind
    body: str
    requested_by: UUID
    run_id: UUID


@dataclass(frozen=True)
class NewChildConversation:
    project_id: UUID
    parent_id: UUID
    task_id: UUID
    title: str
    created_by: UUID
