"""Code -> Korean message table for business errors (roadmap 9.3 rule 2).

Server sentences are never written inline in route or use-case code. A module adds its codes with
``register_error_messages`` when it is imported, and raises errors through ``message_for``. The HTTP
status fallbacks (404, 409, ...) stay in ``errors.HTTP_ERRORS``.
"""

from collections.abc import Mapping

from ramus_api.shared.domain import BusinessError

NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
NOT_IMPLEMENTED_STATUS = 501

_MESSAGES: dict[str, str] = {
    NOT_IMPLEMENTED: "아직 제공하지 않는 기능입니다.",
}


def register_error_messages(messages: Mapping[str, str]) -> None:
    """Adds codes to the table. Re-registering the same sentence is a no-op; a different one is a bug."""
    for code, message in messages.items():
        existing = _MESSAGES.get(code)
        if existing is not None and existing != message:
            raise ValueError(f"Error code {code} already has a different message")
    _MESSAGES.update(messages)


def message_for(code: str) -> str:
    """Returns the sentence for ``code``. Raises ``KeyError`` for an unregistered code."""
    return _MESSAGES[code]


def not_implemented() -> BusinessError:
    """The error every endpoint stub raises until its feature task replaces the handler."""
    return BusinessError(NOT_IMPLEMENTED, message_for(NOT_IMPLEMENTED), status=NOT_IMPLEMENTED_STATUS)
