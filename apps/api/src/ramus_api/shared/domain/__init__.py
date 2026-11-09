"""Shared domain: pure rules and values. Must not import FastAPI or SQLAlchemy."""

from ramus_api.shared.domain.errors import BusinessError
from ramus_api.shared.domain.idempotency import (
    MAX_IDEMPOTENCY_KEY_LENGTH,
    fingerprint,
    idempotency_conflict,
    invalid_idempotency_key,
    is_valid_idempotency_key,
)
from ramus_api.shared.domain.primitives import new_id, utc_now

__all__ = [
    "MAX_IDEMPOTENCY_KEY_LENGTH",
    "BusinessError",
    "fingerprint",
    "idempotency_conflict",
    "invalid_idempotency_key",
    "is_valid_idempotency_key",
    "new_id",
    "utc_now",
]
