"""A bounded Responses call verifies the key and configured model without retaining its response.

Reference: https://developers.openai.com/api/reference/python/resources/responses/methods/create
"""

from collections.abc import Callable

import httpx
from pydantic import BaseModel, ValidationError

from ramus_api.modules.access.application.errors import AI_KEY_INVALID, SERVICE_UNAVAILABLE, AccessRejected


class ValidationResponse(BaseModel):
    status: str
    error: object | None = None


class OpenAiKeyValidator:
    def __init__(self, model: str, *, client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient) -> None:
        self._model = model
        self._client_factory = client_factory

    async def validate(self, api_key: str) -> None:
        try:
            async with self._client_factory(timeout=15.0, follow_redirects=False) as client:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": self._model, "input": "Reply OK.", "max_output_tokens": 16, "store": False},
                )
                if not response.is_success:
                    code = AI_KEY_INVALID if response.status_code in {400, 401, 403, 404, 429} else SERVICE_UNAVAILABLE
                    raise AccessRejected(code)
                result = ValidationResponse.model_validate(response.json())
                # Bounded output may end as incomplete; it still proves model access.
                if result.status not in {"completed", "incomplete"} or result.error is not None:
                    raise AccessRejected(SERVICE_UNAVAILABLE)
        except AccessRejected:
            raise
        except (httpx.HTTPError, ValidationError, ValueError):
            raise AccessRejected(SERVICE_UNAVAILABLE) from None
