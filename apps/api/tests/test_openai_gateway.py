"""Real gateway boundary tested with local HTTP transport and synthetic credentials only."""

import asyncio
import json
import logging
import secrets
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest

from ramus_api.modules.access.public import AccessRejected
from ramus_api.modules.execution.application.output_schema import output_json_schema
from ramus_api.modules.execution.domain.models import LlmFailure, LlmMessage, LlmRequest, RunPurpose
from ramus_api.modules.execution.infrastructure.summary_gateway import MAX_OUTPUT_TOKENS, OpenAiGateway


class Credentials:
    def __init__(self):
        self.key = secrets.token_urlsafe(40)
        self.calls = []
        self.failure = None

    def get_api_key(self, account_id):
        self.calls.append(account_id)
        if self.failure is not None:
            raise self.failure
        return self.key


@pytest.fixture
def credentials():
    return Credentials()


@pytest.fixture
def request_value():
    return LlmRequest(
        RunPurpose.WORK, (LlmMessage("system", "Follow the workflow."), LlmMessage("user", "@AI help")), uuid4()
    )


def completed(text='{"mode":"answer","reply":"Done","tasks":[]}'):
    return {
        "status": "completed", "error": None,
        "output": [{"type": "reasoning", "summary": []}, {
            "type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }],
    }


def gateway_with(credentials, handler):
    return OpenAiGateway("test-model", credentials, client_factory=lambda **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), **kwargs,
    ))


async def test_gateway_sends_exact_schema_and_reads_requesters_current_key(credentials, request_value):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url == "https://api.openai.com/v1/responses"
        assert request.headers["Authorization"] == f"Bearer {credentials.key}"
        payload = json.loads(request.content)
        assert payload == {
            "model": "test-model", "input": [
                {"role": "system", "content": "Follow the workflow."}, {"role": "user", "content": "@AI help"},
            ],
            "text": {"format": {"type": "json_schema", "name": "ramus_output", "strict": True,
                                "schema": output_json_schema(request_value)}},
            "max_output_tokens": MAX_OUTPUT_TOKENS, "store": False,
        }
        assert credentials.key.encode() not in request.content
        return httpx.Response(200, json=completed())

    gateway = gateway_with(credentials, handler)
    output = await gateway.complete(request_value)
    assert output == {"mode": "answer", "reply": "Done", "tasks": ()}
    with pytest.raises(TypeError):
        output["reply"] = "changed"
    credentials.key = secrets.token_urlsafe(40)
    await gateway.complete(request_value)
    assert credentials.calls == [request_value.credential_account_id] * 2
    assert len(calls) == 2


@pytest.mark.parametrize(("changes", "text"), [
    ({"is_child": True}, '{"mode":"answer","reply":"Child reply"}'),
    ({"purpose": RunPurpose.SUMMARY}, '{"conclusion":"Approved conclusion"}'),
])
async def test_gateway_uses_purpose_and_child_output_contract(credentials, request_value, changes, text):
    request_value = replace(request_value, **changes)

    def handler(request):
        schema = json.loads(request.content)["text"]["format"]["schema"]
        assert schema == output_json_schema(request_value)
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
        return httpx.Response(200, json=completed(text))

    assert await gateway_with(credentials, handler).complete(request_value)


@pytest.mark.parametrize(("status", "code", "retryable"), [
    (400, "LLM_UNAVAILABLE", False), (401, "AI_CONNECTION_REQUIRED", False),
    (403, "AI_CONNECTION_REQUIRED", False), (404, "LLM_UNAVAILABLE", False),
    (408, "LLM_UNAVAILABLE", True), (429, "LLM_UNAVAILABLE", True),
    (500, "LLM_UNAVAILABLE", True), (503, "LLM_UNAVAILABLE", True),
    (302, "LLM_UNAVAILABLE", False),
])
async def test_provider_errors_and_redirects_are_sanitized(
    credentials, request_value, status, code, retryable, caplog,
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": credentials.key}},
                              headers={"Location": "https://example.test"})

    with caplog.at_level(logging.DEBUG), pytest.raises(LlmFailure) as error:
        await gateway_with(credentials, handler).complete(request_value)
    assert (error.value.code, error.value.retryable) == (code, retryable)
    assert credentials.key not in str(error.value)
    assert credentials.key not in caplog.text
    assert len(calls) == 1


@pytest.mark.parametrize("body", [
    {}, [], {"status": "completed", "output": []},
    {"status": "incomplete", "output": []}, {"status": "failed", "output": []},
    {"status": "completed", "error": {"message": "provider text"}, "output": []},
    completed("not JSON"), completed('{"mode":"answer","reply":"No tasks field"}'),
    completed('{"mode":"answer","reply":"a","reply":"b","tasks":[]}'),
    completed('{"mode":"branch","reply":"Split","tasks":[]}'),
    {"status": "completed", "output": [{"type": "message", "role": "assistant", "status": "completed",
      "content": [{"type": "refusal", "refusal": "Cannot comply"}]}]},
    {"status": "completed", "output": [{"type": "message", "role": "assistant", "status": "incomplete",
      "content": [{"type": "output_text", "text": "{}"}]}]},
    {"status": "completed", "output": [{"type": "function_call", "arguments": "{}"}]},
])
async def test_refusal_incomplete_empty_and_malformed_output_fail_closed(credentials, request_value, body):
    with pytest.raises(LlmFailure) as error:
        await gateway_with(credentials, lambda _: httpx.Response(200, json=body)).complete(request_value)
    assert error.value.code == "LLM_OUTPUT_INVALID"


async def test_non_json_http_body_fails_closed(credentials, request_value):
    with pytest.raises(LlmFailure) as error:
        await gateway_with(credentials, lambda _: httpx.Response(200, text="invalid")).complete(request_value)
    assert error.value.code == "LLM_OUTPUT_INVALID"


@pytest.mark.parametrize(("exception", "code"), [
    (httpx.ConnectError, "LLM_UNAVAILABLE"), (httpx.ReadTimeout, "LLM_TIMEOUT"),
    (RuntimeError, "LLM_UNAVAILABLE"),
])
async def test_network_and_adapter_errors_do_not_leak_credentials(credentials, request_value, exception, code, caplog):
    def handler(request):
        raise exception(credentials.key)

    with caplog.at_level(logging.DEBUG), pytest.raises(LlmFailure) as error:
        await gateway_with(credentials, handler).complete(request_value)
    assert error.value.code == code
    assert credentials.key not in str(error.value)
    assert credentials.key not in caplog.text


@pytest.mark.parametrize(("failure", "code"), [
    (AccessRejected("AI_CONNECTION_REQUIRED"), "AI_CONNECTION_REQUIRED"),
    (AccessRejected("SERVICE_UNAVAILABLE"), "LLM_UNAVAILABLE"),
    (RuntimeError("untrusted credential adapter text"), "LLM_UNAVAILABLE"),
])
async def test_credential_failure_never_calls_provider(credentials, request_value, failure, code):
    credentials.failure = failure
    called = []
    with pytest.raises(LlmFailure) as error:
        await gateway_with(credentials, lambda _: called.append(True)).complete(request_value)
    assert error.value.code == code
    assert called == []


async def test_cancellation_reaches_pending_http_call(credentials, request_value):
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def handler(request):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    task = asyncio.create_task(gateway_with(credentials, handler).complete(request_value))
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()
