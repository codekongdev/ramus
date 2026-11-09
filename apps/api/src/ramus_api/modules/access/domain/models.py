from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from ramus_api.shared.domain.identity import AuthenticatedAccount as AuthenticatedAccount


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
class MeProfile:
    account: AccountProfile
    default_project_id: UUID
    ai_connection: AIConnectionStatus
