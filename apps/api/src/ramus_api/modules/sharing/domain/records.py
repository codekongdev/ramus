"""Immutable current input metadata and the outcome of a send operation."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ramus_api.modules.sharing.domain.models import InputOrigin


class ShareOutcome(StrEnum):
    LINKED = "linked"
    REPLACED = "replaced"
    UNCHANGED = "unchanged"
    KEPT_NEWER = "kept_newer"


def share_outcome(current_version: int | None, sent_version: int) -> ShareOutcome:
    if current_version is None:
        return ShareOutcome.LINKED
    if current_version < sent_version:
        return ShareOutcome.REPLACED
    if current_version == sent_version:
        return ShareOutcome.UNCHANGED
    return ShareOutcome.KEPT_NEWER


@dataclass(frozen=True)
class SharedTarget:
    conversation_id: UUID
    outcome: ShareOutcome


@dataclass(frozen=True)
class PinnedInput:
    id: UUID
    conversation_id: UUID
    result_id: UUID
    result_revision_id: UUID
    version: int
    title: str
    origin: InputOrigin
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True)
class ReceivedInput:
    pinned: PinnedInput
    latest_version: int
