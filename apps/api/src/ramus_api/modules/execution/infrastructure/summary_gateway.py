"""Account-scoped Responses adapter. Provider payloads and credentials never become errors.

Reference: https://developers.openai.com/api/docs/guides/structured-outputs
"""

import asyncio
from collections.abc import Callable, Mapping
from typing import Annotated, Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ramus_api.modules.access.public import AccessRejected, CredentialProvider
from ramus_api.modules.execution.application.output_schema import output_json_schema, validate_output
from ramus_api.modules.execution.domain.models import LlmFailure, LlmRequest

RESPONSES_URL = "https://api.openai.com/v1/responses"
MAX_OUTPUT_TOKENS = 8192


class ResponseDto(BaseModel):
    model_config = ConfigDict(strict=True)


class ResponseContent(ResponseDto):
    type: Literal["output_text", "refusal"]
    text: str | None = None
    refusal: str | None = None


class ResponseMessage(ResponseDto):
    type: Literal["message"]
    role: Literal["assistant"]
    status: Literal["completed"]
    content: Annotated[list[ResponseContent], Field(min_length=1)]


class ReasoningOutput(ResponseDto):
    type: Literal["reasoning"]


class ResponseEnvelope(ResponseDto):
    status: str
    error: object | None = None
    output: list[Annotated[ResponseMessage | ReasoningOutput, Field(discriminator="type")]]


def response_text(body: Any) -> str:
    """Parse the HTTP envelope before validating the purpose-specific JSON body."""
    try:
        envelope = ResponseEnvelope.model_validate(body)
        if envelope.status != "completed" or envelope.error is not None:
            raise ValueError
        chunks: list[str] = []
        for item in envelope.output:
            if isinstance(item, ResponseMessage):
                for content in item.content:
                    if content.type != "output_text" or content.text is None:
                        raise ValueError
                    chunks.append(content.text)
        raw = "".join(chunks)
        if not raw.strip():
            raise ValueError
        return raw
    except (ValidationError, ValueError, TypeError):
        raise LlmFailure("LLM_OUTPUT_INVALID") from None


class OpenAiGateway:
    def __init__(
        self,
        model: str,
        credentials: CredentialProvider,
        *,
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
    ) -> None:
        self._model = model
        self._credentials = credentials
        self._client_factory = client_factory

    async def complete(self, request: LlmRequest) -> Mapping[str, Any]:
        try:
            # The access use case closes its read transaction before this network call.
            # Read on every call, so disconnecting a key also stops queued work.
            api_key = await asyncio.to_thread(self._credentials.get_api_key, request.credential_account_id)
            async with self._client_factory(
                timeout=httpx.Timeout(100.0, connect=10.0), follow_redirects=False,
            ) as client:
                response = await client.post(
                    RESPONSES_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": self._model,
                        "input": [{"role": item.role, "content": item.content} for item in request.messages],
                        "text": {"format": {
                            "type": "json_schema", "name": "ramus_output", "strict": True,
                            "schema": output_json_schema(request),
                        }},
                        "max_output_tokens": MAX_OUTPUT_TOKENS,
                        "store": False,
                    },
                )
                if response.status_code in {401, 403}:
                    raise LlmFailure("AI_CONNECTION_REQUIRED", retryable=False)
                if not response.is_success:
                    raise LlmFailure(retryable=response.status_code in {408, 409, 429} or response.status_code >= 500)
                try:
                    body = response.json()
                except ValueError:
                    raise LlmFailure("LLM_OUTPUT_INVALID") from None
                return validate_output(request, response_text(body))
        except LlmFailure:
            raise
        except AccessRejected as error:
            code = "AI_CONNECTION_REQUIRED" if error.code == "AI_CONNECTION_REQUIRED" else "LLM_UNAVAILABLE"
            raise LlmFailure(code, retryable=False) from None
        except httpx.TimeoutException:
            raise LlmFailure("LLM_TIMEOUT") from None
        except Exception:
            # Neither HTTP exceptions nor injected credential/client adapters may leak a key.
            # asyncio cancellation is a BaseException and deliberately propagates to the worker.
            raise LlmFailure() from None
