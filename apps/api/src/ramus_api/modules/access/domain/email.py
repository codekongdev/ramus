"""Email address rules for login. Pure functions; no framework imports.

The check is intentionally small (docs/contracts.md 1.1 only needs a deliverable-looking address):
trimmed, lowercased, exactly one ``@``, non-empty local and domain parts, a dot in the domain, and no
whitespace. Delivery itself is the real proof of ownership.
"""

MAX_DISPLAY_NAME_LENGTH = 100
_AT = "@"


class InvalidEmail(ValueError):
    """The address is malformed. The message never contains the submitted address."""

    def __init__(self) -> None:
        super().__init__("Enter a valid email address")


def normalize_email(raw: str) -> str:
    """Returns the canonical form stored in ``account.email`` and ``email_code.email``."""
    email = raw.strip().lower()
    if any(character.isspace() for character in email) or email.count(_AT) != 1:
        raise InvalidEmail()
    local, domain = email.split(_AT)
    if not local or not domain or "." not in domain:
        raise InvalidEmail()
    return email


def display_name_for(email: str) -> str:
    """The initial display name of a new account: the local part, capped to the column length."""
    local, _, _ = email.partition(_AT)
    return local[:MAX_DISPLAY_NAME_LENGTH]
