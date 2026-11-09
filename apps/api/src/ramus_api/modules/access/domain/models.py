from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class AIConnectionStatus(StrEnum):
    NONE = "none"
    CONNECTED = "connected"
    INVALID = "invalid"


class MembershipRole(StrEnum):
    EDITOR = "editor"


@dataclass(frozen=True)
class AccountProfile:
    id: UUID
    email: str
    display_name: str


@dataclass(frozen=True)
class AuthenticatedAccount:
    """The account behind a valid session cookie. Other modules receive this from the access module."""

    account_id: UUID
    email: str
    display_name: str
    session_id: UUID


@dataclass(frozen=True)
class MeProfile:
    account: AccountProfile
    default_project_id: UUID
    ai_connection: AIConnectionStatus
