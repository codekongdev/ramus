from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints


def valid_utf8(value: str) -> str:
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError("텍스트는 유효한 UTF-8 문자열이어야 합니다.") from exc
    return value


SafeText = Annotated[str, StringConstraints(pattern=r"^[^\x00]*$"), AfterValidator(valid_utf8)]
Identifier = Annotated[SafeText, StringConstraints(min_length=1, max_length=36)]
RequestId = Annotated[SafeText, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(DTO):
    email: SafeText = Field(min_length=3, max_length=254)
    password: SafeText = Field(min_length=1, max_length=256)


class CreateProjectRequest(DTO):
    name: Annotated[SafeText, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    request_id: RequestId


class CreateMessageRequest(DTO):
    project_id: Identifier
    conversation_id: Identifier
    content: Annotated[SafeText, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)]
    request_id: RequestId


class UserDTO(DTO):
    id: str
    name: str
    email: str


class ProjectDTO(DTO):
    id: str
    name: str
    instructions: str


class ConversationDTO(DTO):
    id: str
    title: str
    instructions: str
    created_at: str


class MessageDTO(DTO):
    id: str
    conversation_id: str
    author_id: str
    author_name: str
    role: Literal["user"]
    content: str
    sequence: int
    created_at: str


class MessagePostDTO(DTO):
    message: MessageDTO


class StateDTO(DTO):
    user: UserDTO
    project: ProjectDTO
    members: list[UserDTO]
    conversations: list[ConversationDTO]
    messages: list[MessageDTO]


class HealthDTO(DTO):
    status: Literal["ok"]
    service: Literal["ramus"]


class OkDTO(DTO):
    ok: bool


class ErrorDTO(DTO):
    code: str
    message: str
    details: dict | list | None = None


class ErrorResponseDTO(DTO):
    error: ErrorDTO
