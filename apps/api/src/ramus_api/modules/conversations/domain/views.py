"""Immutable conversation values and pure contract projections."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from ramus_api.modules.conversations.domain.models import AuthorKind


@dataclass(frozen=True)
class ConversationRecord:
    id: UUID
    project_id: UUID
    parent_id: UUID | None
    task_id: UUID | None
    title: str
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True)
class MessageRecord:
    id: UUID
    conversation_id: UUID
    seq: int
    author_kind: AuthorKind
    author_account_id: UUID | None
    example_author_label: str | None
    body: str
    requested_by: UUID | None
    run_id: UUID | None
    created_at: datetime


def validate_text(value: str, maximum: int) -> str:
    """Preserves text exactly while rejecting empty/blank and overlong values."""
    if not value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError("Text must be nonblank and within its length limit")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Text must be valid UTF-8") from None
    return value


def mentions_ai(body: str) -> bool:
    return "@ai" in body.lower()


def ancestor_paths(conversations: Iterable[ConversationRecord]) -> dict[UUID, tuple[str, ...]]:
    """Computes root-first ancestor titles, including when records are not in tree order."""
    records = {item.id: item for item in conversations}
    result: dict[UUID, tuple[str, ...]] = {}
    for identifier in records:
        pending: list[UUID] = []
        seen: set[UUID] = set()
        current: UUID | None = identifier
        while current is not None and current not in result:
            if current in seen or current not in records:
                raise ValueError("Conversation ancestry is cyclic or incomplete")
            seen.add(current)
            pending.append(current)
            current = records[current].parent_id
        while pending:
            item = records[pending.pop()]
            if item.parent_id is None:
                result[item.id] = ()
            else:
                parent = records[item.parent_id]
                if parent.project_id != item.project_id:
                    raise ValueError("Conversation ancestors must belong to the same project")
                result[item.id] = (*result[parent.id], parent.title)
    return result


def conversation_json(conversation: ConversationRecord, path: tuple[str, ...]) -> dict[str, Any]:
    return {
        "id": str(conversation.id),
        "project_id": str(conversation.project_id),
        "parent_id": str(conversation.parent_id) if conversation.parent_id else None,
        "task_id": str(conversation.task_id) if conversation.task_id else None,
        "title": conversation.title,
        "path": list(path),
        "created_by": str(conversation.created_by),
        "created_at": conversation.created_at.isoformat(),
    }


def message_json(message: MessageRecord, names: Mapping[UUID, str]) -> dict[str, Any]:
    if message.example_author_label is not None:
        display_name = message.example_author_label
    elif message.author_kind == AuthorKind.HUMAN:
        display_name = names[message.author_account_id]
    else:
        display_name = "AI" if message.author_kind == AuthorKind.AI else "시스템"
    return {
        "id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "seq": message.seq,
        "author": {
            "kind": message.author_kind.value,
            "account_id": str(message.author_account_id) if message.author_account_id else None,
            "display_name": display_name,
        },
        "body": message.body,
        "requested_by": str(message.requested_by) if message.requested_by else None,
        "run_id": str(message.run_id) if message.run_id else None,
        "is_example": message.example_author_label is not None,
        "created_at": message.created_at.isoformat(),
    }
