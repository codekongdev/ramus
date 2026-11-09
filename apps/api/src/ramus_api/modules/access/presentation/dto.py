"""Access DTOs (docs/contracts.md sections 2 and 3.1)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from ramus_api.shared.presentation.schemas import ApiRequest, ApiResponse

MAX_EMAIL_LENGTH = 254
MAX_API_KEY_LENGTH = 512

AiConnectionStatus = Literal["none", "connected", "invalid"]


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
    email: str = Field(min_length=3, max_length=MAX_EMAIL_LENGTH)


class RequestEmailCodeResponse(ApiResponse):
    resend_available_at: datetime


class VerifyEmailCodeRequest(ApiRequest):
    email: str = Field(min_length=3, max_length=MAX_EMAIL_LENGTH)
    code: str = Field(pattern=r"^\d{6}$")


class ConnectAiRequest(ApiRequest):
    api_key: str = Field(min_length=1, max_length=MAX_API_KEY_LENGTH)
