"""``Idempotency-Key`` header dependency for change routes."""

from typing import Annotated

from fastapi import Depends, Header

from ramus_api.shared.domain import (
    MAX_IDEMPOTENCY_KEY_LENGTH,
    invalid_idempotency_key,
    is_valid_idempotency_key,
)

IDEMPOTENCY_HEADER = "Idempotency-Key"


def require_idempotency_key(
    value: Annotated[
        str | None,
        Header(
            alias=IDEMPOTENCY_HEADER,
            description=(
                f"Required. 1-{MAX_IDEMPOTENCY_KEY_LENGTH} characters of [A-Za-z0-9._:-]. "
                "Reusing a key with the same body replays the stored response."
            ),
        ),
    ] = None,
) -> str:
    # Optional at the schema level so a missing header yields 400 IDEMPOTENCY_KEY_INVALID, not 422.
    if value is None or not is_valid_idempotency_key(value):
        raise invalid_idempotency_key()
    return value


IdempotencyKey = Annotated[str, Depends(require_idempotency_key)]
