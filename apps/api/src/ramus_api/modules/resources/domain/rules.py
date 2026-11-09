"""Pure rules for shared skills/materials (F-08·F-09, D9). No I/O, no framework imports."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ramus_api.modules.resources.domain.models import ResourceKind

MAX_NAME_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 2_000
MAX_TEXT_LENGTH = 100_000
MAX_FILE_NAME_LENGTH = 255
ALLOWED_FILE_EXTENSIONS = (".md", ".txt")

INVALID_INPUT = "INVALID_INPUT"
FILE_TYPE_UNSUPPORTED = "FILE_TYPE_UNSUPPORTED"
NOT_FOUND = "NOT_FOUND"


class ResourceRuleError(Exception):
    """An expected failure. Presentation turns ``code`` into the user-facing sentence."""

    def __init__(self, code: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.details = details


@dataclass(frozen=True)
class RevisionContent:
    """The user-authored part of one immutable revision, already normalized."""

    name: str
    description: str
    instructions: str | None
    content: str | None
    file_name: str | None


def _invalid(field: str, reason: str) -> ResourceRuleError:
    return ResourceRuleError(INVALID_INPUT, {"field": field, "reason": reason})


def _required_text(field: str, value: str | None, limit: int) -> str:
    text = (value or "").strip()
    if not text:
        raise _invalid(field, "required")
    if len(text) > limit:
        raise _invalid(field, "too_long")
    return text


def _absent(field: str, value: str | None) -> None:
    if value is not None:
        raise _invalid(field, "not_allowed")


def normalize_content(
    kind: ResourceKind,
    *,
    name: str,
    description: str,
    instructions: str | None,
    content: str | None,
    file_name: str | None,
) -> RevisionContent:
    """Validates one revision for ``kind`` and trims surrounding whitespace.

    skill: instructions only. text: content only. file: content plus a ``.md``/``.txt`` name.
    """
    clean_name = _required_text("name", name, MAX_NAME_LENGTH)
    clean_description = (description or "").strip()
    if len(clean_description) > MAX_DESCRIPTION_LENGTH:
        raise _invalid("description", "too_long")

    if kind is ResourceKind.SKILL:
        _absent("content", content)
        _absent("file_name", file_name)
        return RevisionContent(
            clean_name,
            clean_description,
            _required_text("instructions", instructions, MAX_TEXT_LENGTH),
            None,
            None,
        )

    _absent("instructions", instructions)
    if kind is ResourceKind.TEXT:
        _absent("file_name", file_name)
        return RevisionContent(
            clean_name, clean_description, None, _required_text("content", content, MAX_TEXT_LENGTH), None
        )

    clean_file_name = _required_text("file_name", file_name, MAX_FILE_NAME_LENGTH)
    if not clean_file_name.lower().endswith(ALLOWED_FILE_EXTENSIONS):
        raise ResourceRuleError(FILE_TYPE_UNSUPPORTED, {"file_name": clean_file_name})
    body = _required_text("content", content, MAX_TEXT_LENGTH)
    if "\x00" in body:  # NUL never appears in UTF-8 text files; it marks binary input.
        raise ResourceRuleError(FILE_TYPE_UNSUPPORTED, {"file_name": clean_file_name})
    return RevisionContent(clean_name, clean_description, None, body, clean_file_name)


def content_hash(content: RevisionContent) -> str:
    """Stable digest of the authored fields, used to detect an unchanged re-save (B2)."""
    canonical = json.dumps(
        [content.name, content.description, content.instructions, content.content, content.file_name],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RevisionRef:
    revision_id: UUID
    resource_id: UUID
    project_id: UUID


def check_applied_selection(
    requested: Iterable[UUID], found: Iterable[RevisionRef], project_id: UUID
) -> tuple[RevisionRef, ...]:
    """The revisions a conversation may pin: all exist in ``project_id``, one per resource.

    Returns them in request order with exact duplicates removed. Unknown ids and ids from another
    project are reported together so the caller cannot tell them apart.
    """
    by_id = {ref.revision_id: ref for ref in found}
    ordered = tuple(dict.fromkeys(requested))
    unknown = [rid for rid in ordered if rid not in by_id or by_id[rid].project_id != project_id]
    if unknown:
        raise ResourceRuleError(
            INVALID_INPUT, {"field": "revision_ids", "reason": "unknown", "ids": [str(i) for i in unknown]}
        )
    refs = tuple(by_id[rid] for rid in ordered)
    seen: set[UUID] = set()
    for ref in refs:
        if ref.resource_id in seen:
            raise ResourceRuleError(
                INVALID_INPUT,
                {
                    "field": "revision_ids",
                    "reason": "one_revision_per_resource",
                    "resource_id": str(ref.resource_id),
                },
            )
        seen.add(ref.resource_id)
    return refs
