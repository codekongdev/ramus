from enum import StrEnum


class AIConnectionStatus(StrEnum):
    NONE = "none"
    CONNECTED = "connected"
    INVALID = "invalid"


class MembershipRole(StrEnum):
    EDITOR = "editor"
