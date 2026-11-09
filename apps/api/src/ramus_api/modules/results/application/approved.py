"""Immutable approved-conclusion boundary, without drafts or source resource contents."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ApprovedConclusion:
    id: UUID
    result_id: UUID
    project_id: UUID
    version: int
    latest_version: int
    title: str
    conclusion: str
    source: dict[str, Any]
