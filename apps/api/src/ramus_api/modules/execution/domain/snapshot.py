"""The single place that converts run input snapshots to and from their JSONB form."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from ramus_api.modules.execution.domain.models import ConversationContext, LlmRequest, RunInputSnapshot

EMPTY_SNAPSHOT = RunInputSnapshot()

_SEQ_KEYS = ("message_from_seq", "message_to_seq")
_ID_KEYS = ("resource_revision_ids", "input_result_revision_ids")


def snapshot_from_context(
    context: ConversationContext, request: LlmRequest | None = None
) -> RunInputSnapshot:
    """Pins the message range and revision IDs actually read; never stores bodies."""
    return RunInputSnapshot(
        message_from_seq=request.message_from_seq if request is not None else None,
        message_to_seq=request.message_to_seq if request is not None else None,
        resource_revision_ids=tuple(item.revision_id for item in context.resources),
        input_result_revision_ids=tuple(item.result_revision_id for item in context.results),
    )


def snapshot_to_json(snapshot: RunInputSnapshot) -> dict[str, Any]:
    return {
        "message_from_seq": snapshot.message_from_seq,
        "message_to_seq": snapshot.message_to_seq,
        "resource_revision_ids": [str(item) for item in snapshot.resource_revision_ids],
        "input_result_revision_ids": [str(item) for item in snapshot.input_result_revision_ids],
    }


def _seq(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Message sequence must be an integer or null")
    return value


def _ids(value: Any) -> tuple[UUID, ...]:
    if not isinstance(value, list):
        raise ValueError("Revision IDs must be a list")
    if not all(isinstance(item, str) for item in value):
        raise ValueError("Revision IDs must be strings")
    return tuple(UUID(item) for item in value)


def snapshot_from_json(value: Any) -> RunInputSnapshot:
    """Strict inverse of ``snapshot_to_json``. Raises ``ValueError`` for any other shape."""
    if not isinstance(value, Mapping) or set(value) != {*_SEQ_KEYS, *_ID_KEYS}:
        raise ValueError("Run input snapshot has an unexpected shape")
    return RunInputSnapshot(
        message_from_seq=_seq(value["message_from_seq"]),
        message_to_seq=_seq(value["message_to_seq"]),
        resource_revision_ids=_ids(value["resource_revision_ids"]),
        input_result_revision_ids=_ids(value["input_result_revision_ids"]),
    )
