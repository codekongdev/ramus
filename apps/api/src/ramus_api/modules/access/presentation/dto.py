"""Access DTOs (docs/contracts.md sections 2 and 3.1)."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, Field, SecretStr, field_validator

from ramus_api.modules.access.domain.email import MAX_EMAIL_LENGTH, normalize_email
from ramus_api.shared.presentation.schemas import ApiRequest, ApiResponse

MAX_API_KEY_LENGTH = 512

AiConnectionStatus = Literal["none", "connected", "invalid"]

# Normalized (trimmed, lowercased) at the boundary; a malformed address is 422 INVALID_INPUT.
EmailAddress = Annotated[
    str, Field(min_length=3, max_length=MAX_EMAIL_LENGTH), AfterValidator(normalize_email)
]


class Account(ApiResponse):
    id: UUID
    email: str
    display_name: str


class AiConnectionState(ApiResponse):
    status: AiConnectionStatus


class AiConnectionConnected(ApiResponse):
    status: Literal["connected"]


class AiConnectionDisconnected(ApiResponse):
    status: Literal["none"]


class Me(ApiResponse):
    account: Account
    default_project_id: UUID
    ai_connection: AiConnectionState


class RequestEmailCodeRequest(ApiRequest):
    email: EmailAddress


class RequestEmailCodeResponse(ApiResponse):
    resend_available_at: datetime


class VerifyEmailCodeRequest(ApiRequest):
    email: EmailAddress
    code: str = Field(pattern=r"^[0-9]{6}$")


class ConnectAiRequest(ApiRequest):
    api_key: str = Field(min_length=1, max_length=MAX_API_KEY_LENGTH, repr=False)


class PasswordValueRequest(ApiRequest):
    password: SecretStr = Field(min_length=12, max_length=128, repr=False)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        password = value.get_secret_value()
        if "\x00" in password:
            raise ValueError("Password contains an invalid character")
        try:
            password.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Password must be valid UTF-8") from None
        return value


class PasswordLoginRequest(PasswordValueRequest):
    email: EmailAddress


class SetInitialPasswordRequest(PasswordValueRequest):
    pass


class PasswordState(ApiResponse):
    configured: bool


class PasswordConfigured(ApiResponse):
    configured: Literal[True]


class RegisterAccountRequest(PasswordLoginRequest):
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        import unicodedata

        value = value.strip()
        if not value or any(unicodedata.category(char).startswith("C") for char in value):
            raise ValueError("Display name must contain visible text without control characters")
        return value
