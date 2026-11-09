"""Identity returned after resolving a session, shared across feature boundaries."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AuthenticatedAccount:
    """The account behind a valid session cookie. Other modules receive this from the access module."""

    account_id: UUID
    email: str
    display_name: str
    session_id: UUID
