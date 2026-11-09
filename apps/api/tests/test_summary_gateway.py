"""The production adapter is exercised through an in-memory HTTP transport only."""

import json
from uuid import uuid4

import httpx
import pytest

from ramus_api.modules.execution.domain.models import LlmFailure, LlmMessage, LlmRequest, RunPurpose
from ramus_api.modules.execution.infrastructure.summary_gateway import OpenAiGateway


class Credentials:
    def __init__(self):
        self.accounts = []

    def get_api_key(self, account_id):
        self.accounts.append(account_id)
        return "synthetic-fixture-key"


def response(raw='{"conclusion":"검토할 결론"}', **values):
    return {"status": "completed", "error": None, "output": [{
        "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": raw}],
    }], **values}


def gateway(handler, credentials=None):
    return OpenAiGateway("configured-model", credentials or Credentials(), client_factory=lambda **options:
                         httpx.AsyncClient(transport=httpx.MockTransport(handler), **options))


def request(purpose=RunPurpose.SUMMARY):
    return LlmRequest(purpose, (LlmMessage("system", "Return a conclusion."), LlmMessage("user", "source")), uuid4())


@pytest.mark.parametrize("purpose,raw", [
    (RunPurpose.SUMMARY, '{"conclusion":"검토할 결론"}'),
    (RunPurpose.WORK, '{"mode":"answer","reply":"검토할 응답","tasks":[]}'),
])
async def test_uses_the_requesting_account_and_strict_schema_without_storing_provider_data(purpose, raw):
    calls, credentials = [], Credentials()

    def handle(http_request):
        calls.append(http_request)
        return httpx.Response(200, json=response(raw))

    value = request(purpose)
    output = await gateway(handle, credentials).complete(value)
    assert dict(output) == json.loads(raw) or output["reply"] == "검토할 응답"
    assert credentials.accounts == [value.credential_account_id]
    [call] = calls
    assert str(call.url) == "https://api.openai.com/v1/responses"
    body = json.loads(call.content)
    assert body["model"] == "configured-model" and body["store"] is False
    assert body["text"]["format"]["strict"] is True
    assert body["text"]["format"]["schema"]["additionalProperties"] is False
    assert body["input"] == [{"role": "system", "content": "Return a conclusion."}, {"role": "user", "content": "source"}]
    if purpose == RunPurpose.SUMMARY:
        assert set(body["text"]["format"]["schema"]["properties"]) == {"conclusion"}


@pytest.mark.parametrize("payload", [
    response('{"conclusion":"first","conclusion":"second"}'),
    response('{"conclusion":"valid","reasoning":"private"}'),
    response('{"conclusion":"   "}'),
    {"status": "completed", "output": [{"type": "message", "role": "assistant", "content": [{"type": "refusal"}]}]},
    {"status": "completed", "output": []},
    {"status": "completed", "output": "malformed"},
])
async def test_rejects_invalid_output_without_exposing_response(payload):
    with pytest.raises(LlmFailure) as caught:
        await gateway(lambda _: httpx.Response(200, json=payload)).complete(request())
    assert caught.value.code == "LLM_OUTPUT_INVALID"
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("status,code", [(401, "AI_CONNECTION_REQUIRED"), (403, "AI_CONNECTION_REQUIRED"), (429, "LLM_UNAVAILABLE"), (500, "LLM_UNAVAILABLE")])
async def test_provider_errors_are_sanitized(status, code):
    with pytest.raises(LlmFailure) as caught:
        await gateway(lambda _: httpx.Response(status, text="synthetic-fixture-key private-provider-error")).complete(request())
    assert caught.value.code == code
    assert "synthetic" not in str(caught.value) and "private" not in str(caught.value)


async def test_incomplete_output_never_becomes_an_approved_draft():
    with pytest.raises(LlmFailure) as caught:
        await gateway(lambda _: httpx.Response(200, json=response(status="incomplete"))).complete(request())
    assert caught.value.code == "LLM_UNAVAILABLE"


async def test_missing_credentials_never_send_an_http_request():
    class MissingCredentials:
        def get_api_key(self, _account):
            raise ValueError("private credential failure")

    def unexpected(_):
        pytest.fail("A keyless request must never reach the provider")

    with pytest.raises(LlmFailure) as caught:
        await gateway(unexpected, MissingCredentials()).complete(request())
    assert caught.value.code == "AI_CONNECTION_REQUIRED"


async def test_timeout_is_bounded_and_sanitized():
    def timeout(http_request):
        raise httpx.ReadTimeout("private timeout details", request=http_request)

    with pytest.raises(LlmFailure) as caught:
        await gateway(timeout).complete(request())
    assert caught.value.code == "LLM_TIMEOUT"
