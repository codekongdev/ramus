"""Pure idempotency rules: key format, request fingerprint, and the conflict error."""

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from ramus_api.shared.domain.errors import BusinessError

MAX_IDEMPOTENCY_KEY_LENGTH = 128
_KEY_PATTERN = re.compile(rf"[A-Za-z0-9._:-]{{1,{MAX_IDEMPOTENCY_KEY_LENGTH}}}")


def is_valid_idempotency_key(key: str) -> bool:
    return _KEY_PATTERN.fullmatch(key) is not None


def _encode_non_json(value: object) -> Any:
    """Encodes values that ``model_dump()`` commonly returns but JSON lacks. ``date`` covers ``datetime``."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID | Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Cannot fingerprint a value of type {type(value).__name__}")


def fingerprint(payload: Mapping[str, Any]) -> str:
    """SHA-256 of the payload as canonical JSON (sorted keys at every depth).

    UUID and Decimal become strings, date/datetime become ISO 8601, Enum becomes its value.
    Any other non-JSON type raises TypeError naming the type.
    """
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=_encode_non_json
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def idempotency_conflict() -> BusinessError:
    return BusinessError(
        "IDEMPOTENCY_CONFLICT",
        "같은 요청 키로 다른 내용을 보낼 수 없습니다. 새 요청으로 다시 시도해 주세요.",
        409,
    )


def invalid_idempotency_key() -> BusinessError:
    return BusinessError(
        "IDEMPOTENCY_KEY_INVALID",
        "요청 키가 없거나 형식이 올바르지 않습니다.",
        400,
        {"header": "Idempotency-Key", "max_length": MAX_IDEMPOTENCY_KEY_LENGTH, "allowed": "A-Z a-z 0-9 . _ : -"},
    )
