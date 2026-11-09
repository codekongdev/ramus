"""Expected login failures. Presentation maps each code to its status and user-facing sentence."""

from typing import Any

AUTH_CODE_INVALID = "AUTH_CODE_INVALID"
AUTH_CODE_EXPIRED = "AUTH_CODE_EXPIRED"
AUTH_RATE_LIMITED = "AUTH_RATE_LIMITED"
AI_KEY_INVALID = "AI_KEY_INVALID"
AI_CONNECTION_REQUIRED = "AI_CONNECTION_REQUIRED"
SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class AccessRejected(Exception):
    """A business rule rejected the request. ``details`` must never contain codes or tokens."""

    def __init__(self, code: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.details = details
