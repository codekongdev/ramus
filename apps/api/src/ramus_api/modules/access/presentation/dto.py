"""Access DTOs (docs/contracts.md sections 2 and 3.1)."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, Field

from ramus_api.modules.access.domain.email import normalize_email
from ramus_api.shared.presentation.schemas import ApiRequest, ApiResponse

MAX_EMAIL_LENGTH = 254
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
    code: str = Field(pattern=r"^\d{6}$")


class ConnectAiRequest(ApiRequest):
    api_key: str = Field(min_length=1, max_length=MAX_API_KEY_LENGTH)
