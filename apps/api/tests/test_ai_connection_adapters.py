"""Credential cryptography and the remote API boundary, without external calls."""

import json
import logging
import secrets
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from ramus_api.modules.access.application.errors import AccessRejected
from ramus_api.modules.access.infrastructure.credential_cipher import AesCredentialCipher
from ramus_api.modules.access.infrastructure.openai_key_validator import OpenAiKeyValidator
from ramus_api.modules.access.presentation.dto import ConnectAiRequest
from ramus_api.settings import Settings


@pytest.fixture
def cipher() -> AesCredentialCipher:
    return AesCredentialCipher(SecretStr(secrets.token_urlsafe(32)))


def test_cipher_is_randomized_authenticated_and_account_bound(cipher: AesCredentialCipher) -> None:
    owner, other = uuid4(), uuid4()
    key = secrets.token_urlsafe(40)
    first, second = cipher.encrypt(owner, key), cipher.encrypt(owner, key)
    assert first != second
    assert key not in first
    assert cipher.decrypt(owner, first) == key
    assert cipher.fingerprint(key) == cipher.fingerprint(key)
    assert key not in cipher.fingerprint(key)
    for account, ciphertext in ((other, first), (owner, first[:-8] + 'AAAAAAA='), (owner, 'invalid')):
        with pytest.raises(AccessRejected) as error:
            cipher.decrypt(account, ciphertext)
        assert error.value.code == 'SERVICE_UNAVAILABLE'
        assert key not in str(error.value)


@pytest.mark.parametrize('secret', [None, SecretStr('bad'), SecretStr(secrets.token_urlsafe(16))])
def test_cipher_fails_closed_for_missing_or_invalid_server_secret(secret) -> None:
    with pytest.raises(AccessRejected) as error:
        AesCredentialCipher(secret).encrypt(uuid4(), secrets.token_urlsafe(40))
    assert error.value.code == 'SERVICE_UNAVAILABLE'


def test_server_secret_and_incoming_key_are_excluded_from_repr() -> None:
    secret, key = secrets.token_urlsafe(32), secrets.token_urlsafe(40)
    settings = Settings(_env_file=None, RAMUS_SECRET_KEY=secret)
    assert secret not in repr(settings)
    assert key not in repr(ConnectAiRequest(api_key=key))


def validator_with(handler, model='test-model') -> OpenAiKeyValidator:
    return OpenAiKeyValidator(model, client_factory=lambda **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), **kwargs
    ))


@pytest.mark.parametrize('status', ['completed', 'incomplete'])
async def test_validation_uses_bounded_model_call_without_storing_response(status) -> None:
    key = secrets.token_urlsafe(40)
    calls = []

    def handle(request):
        calls.append(request)
        assert request.url == 'https://api.openai.com/v1/responses'
        assert request.headers['Authorization'] == f'Bearer {key}'
        assert json.loads(request.content) == {
            'model': 'test-model', 'input': 'Reply OK.', 'max_output_tokens': 16, 'store': False
        }
        assert key.encode() not in request.content
        return httpx.Response(200, json={'status': status, 'error': None, 'output': []})

    await validator_with(handle).validate(key)
    assert len(calls) == 1


@pytest.mark.parametrize(('status', 'code'), [
    (400, 'AI_KEY_INVALID'), (401, 'AI_KEY_INVALID'), (403, 'AI_KEY_INVALID'),
    (404, 'AI_KEY_INVALID'), (429, 'AI_KEY_INVALID'), (500, 'SERVICE_UNAVAILABLE'),
    (503, 'SERVICE_UNAVAILABLE'), (302, 'SERVICE_UNAVAILABLE')
])
async def test_provider_errors_are_sanitized_and_never_follow_redirects(status, code, caplog) -> None:
    key = secrets.token_urlsafe(40)
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, json={'error': {'message': key}}, headers={'Location': 'https://example.test'})

    with caplog.at_level(logging.DEBUG), pytest.raises(AccessRejected) as error:
        await validator_with(handle).validate(key)
    assert error.value.code == code
    assert key not in str(error.value)
    assert key not in caplog.text
    assert len(calls) == 1


@pytest.mark.parametrize('body', [
    {}, [], {'status': 42}, {'status': 'failed', 'error': None},
    {'status': 'completed', 'error': {'message': 'untrusted provider text'}}
])
async def test_malformed_or_unsuccessful_provider_output_is_not_a_success(body) -> None:
    with pytest.raises(AccessRejected) as error:
        await validator_with(lambda _: httpx.Response(200, json=body)).validate(secrets.token_urlsafe(40))
    assert error.value.code == 'SERVICE_UNAVAILABLE'


async def test_network_error_is_sanitized(caplog) -> None:
    key = secrets.token_urlsafe(40)

    def handle(request):
        raise httpx.ConnectError(key, request=request)

    with caplog.at_level(logging.DEBUG), pytest.raises(AccessRejected) as error:
        await validator_with(handle).validate(key)
    assert error.value.code == 'SERVICE_UNAVAILABLE'
    assert key not in str(error.value)
    assert key not in caplog.text
