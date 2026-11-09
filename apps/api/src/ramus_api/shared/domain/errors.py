from __future__ import annotations

from typing import Any

DEFAULT_BUSINESS_ERROR_STATUS = 400


class BusinessError(Exception):
    """An expected, user-facing failure. ``message`` is a Korean sentence shown to the user."""

    def __init__(
        self,
        code: str,
        message: str,
        status: int = DEFAULT_BUSINESS_ERROR_STATUS,
        details: dict[str, Any] | list[Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details
