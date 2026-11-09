"""Account-only connection API and storage against throwaway PostgreSQL; no OpenAI calls."""

import logging
import secrets
from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from login_flow import error_code, login, new_key, unique_email
from pydantic import SecretStr
from test_access_session_integration import stored_values_containing

from ramus_api.main import create_app
from ramus_api.modules.access.application.errors import AI_KEY_INVALID, AccessRejected
from ramus_api.modules.access.composition import build_ai_connections
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.access.infrastructure.models import AIConnectionRow
from ramus_api.settings import Settings

pytestmark = pytest.mark.integration
PATH = '/api/me/ai-connection'


class FakeKeyValidator:
    def __init__(self) -> None:
        self.calls = 0
        self.failure: str | None = None

    async def validate(self, api_key: str) -> None:
        self.calls += 1
        if self.failure:
            raise AccessRejected(self.failure)


@pytest.fixture
def validator() -> FakeKeyValidator:
    return FakeKeyValidator()


@pytest.fixture
def mailer() -> FakeMailer:
    return FakeMailer()


@pytest.fixture
def app(integration_settings: Settings, mailer: FakeMailer, validator: FakeKeyValidator) -> FastAPI:
    settings = integration_settings.model_copy(update={'secret_key': SecretStr(secrets.token_urlsafe(32))})
    return create_app(settings, mailer=mailer, ai_key_validator=validator)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as instance:
        yield instance


def connect(client, key=None, headers=None):
    return client.put(PATH, json={'api_key': key or secrets.token_urlsafe(40)}, headers=headers or new_key('ai'))


@pytest.mark.parametrize('method', ['get', 'put', 'delete'])
def test_connection_endpoints_require_login(client, validator, method) -> None:
    kwargs = {'headers': new_key()}
    if method == 'put':
        kwargs['json'] = {'api_key': secrets.token_urlsafe(40)}
    response = client.request(method, PATH, **kwargs)
    assert response.status_code == 401
    assert error_code(response) == 'UNAUTHORIZED'
    assert validator.calls == 0


def test_connect_replace_disconnect_and_executor_lookup(client, app, mailer, validator) -> None:
    me = login(client, mailer, unique_email('ai-life')).json()
    account_id = UUID(me['account']['id'])
    credentials = build_ai_connections(app.state.container)
    first, second = secrets.token_urlsafe(40), secrets.token_urlsafe(40)
    assert client.get(PATH).json() == {'status': 'none'}
    assert connect(client, first).json() == {'status': 'connected'}
    assert client.get('/api/me').json()['ai_connection'] == {'status': 'connected'}
    assert credentials.get_api_key(account_id) == first
    with app.state.container.database.transaction() as session:
        assert credentials.is_connected(session, account_id)
    assert connect(client, second).json() == {'status': 'connected'}
    assert credentials.get_api_key(account_id) == second
    response = client.delete(PATH, headers=new_key())
    assert response.status_code == 200
    assert response.json() == {'status': 'none'}
    assert client.get('/api/me').json()['ai_connection'] == {'status': 'none'}
    with app.state.container.database.transaction() as session:
        assert not credentials.is_connected(session, account_id)
        assert session.get(AIConnectionRow, account_id) is None
    with pytest.raises(AccessRejected) as error:
        credentials.get_api_key(account_id)
    assert error.value.code == 'AI_CONNECTION_REQUIRED'
    assert validator.calls == 2


def test_invalid_replacement_preserves_previous_key(client, app, mailer, validator) -> None:
    me = login(client, mailer, unique_email('ai-replace')).json()
    key = secrets.token_urlsafe(40)
    assert connect(client, key).status_code == 200
    validator.failure = AI_KEY_INVALID
    response = connect(client)
    assert response.status_code == 422
    assert error_code(response) == AI_KEY_INVALID
    assert client.get(PATH).json() == {'status': 'connected'}
    assert build_ai_connections(app.state.container).get_api_key(UUID(me['account']['id'])) == key


def test_invalid_initial_connection_is_recoverable(client, mailer, validator) -> None:
    login(client, mailer, unique_email('ai-invalid'))
    validator.failure = AI_KEY_INVALID
    assert connect(client).status_code == 422
    assert client.get(PATH).json() == {'status': 'none'}
    assert client.get('/api/me').status_code == 200
    validator.failure = None
    assert connect(client).status_code == 200


def test_account_isolation_in_state_credentials_and_disconnect(client, app, mailer) -> None:
    me = login(client, mailer, unique_email('ai-owner')).json()
    owner = UUID(me['account']['id'])
    key = secrets.token_urlsafe(40)
    assert connect(client, key).status_code == 200
    with TestClient(app) as other:
        other_me = login(other, mailer, unique_email('ai-other')).json()
        assert other.get(PATH).json() == {'status': 'none'}
        assert key not in other.get('/api/me').text
        assert other.delete(PATH, headers=new_key()).json() == {'status': 'none'}
        with pytest.raises(AccessRejected):
            build_ai_connections(app.state.container).get_api_key(UUID(other_me['account']['id']))
    assert client.get(PATH).json() == {'status': 'connected'}
    assert build_ai_connections(app.state.container).get_api_key(owner) == key


def test_idempotency_replays_without_replacing_or_duplicating_and_rejects_conflict(client, app, mailer) -> None:
    me = login(client, mailer, unique_email('ai-idempotent')).json()
    account_id = UUID(me['account']['id'])
    key, headers = secrets.token_urlsafe(40), new_key()
    assert connect(client, key, headers).json() == {'status': 'connected'}
    with app.state.container.database.transaction() as session:
        ciphertext = session.get(AIConnectionRow, account_id).ciphertext
    assert connect(client, key, headers).json() == {'status': 'connected'}
    with app.state.container.database.transaction() as session:
        assert session.get(AIConnectionRow, account_id).ciphertext == ciphertext
    response = connect(client, headers=headers)
    assert response.status_code == 409
    assert error_code(response) == 'IDEMPOTENCY_CONFLICT'
    delete_headers = new_key()
    assert client.delete(PATH, headers=delete_headers).json() == {'status': 'none'}
    assert client.delete(PATH, headers=delete_headers).json() == {'status': 'none'}


def test_key_is_absent_from_responses_all_database_text_and_logs(client, app, mailer, caplog) -> None:
    me = login(client, mailer, unique_email('ai-secret')).json()
    key = secrets.token_urlsafe(40)
    with caplog.at_level(logging.DEBUG):
        connected = connect(client, key)
        state = client.get(PATH)
        profile = client.get('/api/me')
    assert connected.status_code == 200
    for response in (connected, state, profile):
        assert key not in response.text
    assert key not in caplog.text
    assert stored_values_containing(app, key) == []
    with app.state.container.database.transaction() as session:
        ciphertext = session.get(AIConnectionRow, UUID(me['account']['id'])).ciphertext
    assert ciphertext != key
    assert key not in ciphertext


def test_bad_validation_body_does_not_echo_key(client, mailer) -> None:
    login(client, mailer, unique_email('ai-body'))
    key = secrets.token_urlsafe(400)
    response = client.put(PATH, json={'api_key': key}, headers=new_key())
    assert response.status_code == 422
    assert key not in response.text


def test_missing_server_secret_fails_before_validation(integration_settings, mailer, validator) -> None:
    settings = integration_settings.model_copy(update={'secret_key': None})
    with TestClient(create_app(settings, mailer=mailer, ai_key_validator=validator)) as client:
        login(client, mailer, unique_email('ai-missing-secret'))
        response = connect(client)
        assert response.status_code == 503
        assert error_code(response) == 'SERVICE_UNAVAILABLE'
        assert client.get(PATH).json() == {'status': 'none'}
    assert validator.calls == 0


def test_untrusted_provider_exception_is_sanitized(integration_settings, mailer, caplog) -> None:
    key = secrets.token_urlsafe(40)

    class BrokenValidator:
        async def validate(self, api_key):
            raise RuntimeError(api_key)

    settings = integration_settings.model_copy(update={'secret_key': SecretStr(secrets.token_urlsafe(32))})
    with TestClient(create_app(settings, mailer=mailer, ai_key_validator=BrokenValidator())) as client:
        login(client, mailer, unique_email('ai-broken'))
        with caplog.at_level(logging.DEBUG):
            response = connect(client, key)
        assert response.status_code == 503
        assert key not in response.text
        assert key not in caplog.text
        assert client.get(PATH).json() == {'status': 'none'}


def test_invalid_saved_connection_is_not_usable_by_executor(client, app, mailer) -> None:
    me = login(client, mailer, unique_email('ai-invalid-stored')).json()
    account_id = UUID(me['account']['id'])
    assert connect(client).status_code == 200
    with app.state.container.database.transaction() as session:
        row = session.get(AIConnectionRow, account_id)
        row.status = 'invalid'
    assert client.get(PATH).json() == {'status': 'invalid'}
    credentials = build_ai_connections(app.state.container)
    with app.state.container.database.transaction() as session:
        assert not credentials.is_connected(session, account_id)
    with pytest.raises(AccessRejected):
        credentials.get_api_key(account_id)
