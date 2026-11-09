"""Account-scoped Responses gateway; credentials and provider payloads never escape errors.

https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses
"""

import asyncio
from collections.abc import Callable, Mapping
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from ramus_api.modules.access.application.ports import CredentialProvider
from ramus_api.modules.execution.application.output_schema import output_json_schema, validate_output
from ramus_api.modules.execution.domain.models import LlmFailure, LlmRequest


class ResponseContent(BaseModel):
    type: str
    text: str | None = None


class ResponseItem(BaseModel):
    type: str
    role: str | None = None
    content: list[ResponseContent] = Field(default_factory=list)


class ModelResponse(BaseModel):
    status: str
    error: object | None = None
    output: list[ResponseItem]


class OpenAiGateway:
    def __init__(
        self, model: str, credentials: CredentialProvider,
        *, client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
    ) -> None:
        self._model, self._credentials, self._client_factory = model, credentials, client_factory

    async def complete(self, request: LlmRequest) -> Mapping[str, Any]:
        try:
            api_key = await asyncio.to_thread(self._credentials.get_api_key, request.credential_account_id)
        except Exception:
            raise LlmFailure("AI_CONNECTION_REQUIRED") from None
        try:
            async with self._client_factory(timeout=110.0, follow_redirects=False) as client:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": self._model, "store": False,
                        "input": [{"role": item.role, "content": item.content} for item in request.messages],
                        "text": {"format": {
                            "type": "json_schema", "name": f"ramus_{request.purpose.value}",
                            "strict": True, "schema": output_json_schema(request),
                        }},
                    },
                )
                if response.status_code in {401, 403}:
                    raise LlmFailure("AI_CONNECTION_REQUIRED")
                if not response.is_success:
                    raise LlmFailure()
                result = ModelResponse.model_validate(response.json())
                if result.status != "completed" or result.error is not None:
                    raise LlmFailure()
                contents = [part for item in result.output if item.type == "message" and item.role == "assistant"
                            for part in item.content]
                if len(contents) != 1 or contents[0].type != "output_text" or contents[0].text is None:
                    raise LlmFailure("LLM_OUTPUT_INVALID")
                return validate_output(request, contents[0].text)
        except LlmFailure:
            raise
        except httpx.TimeoutException:
            raise LlmFailure("LLM_TIMEOUT") from None
        except (ValidationError, ValueError, TypeError):
            raise LlmFailure("LLM_OUTPUT_INVALID") from None
        except Exception:
            raise LlmFailure() from None
