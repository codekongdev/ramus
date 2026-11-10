"""Session cookie, current-account lookup, logout, and secret storage against PostgreSQL."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from login_flow import (
    ME_PATH,
    SESSION_COOKIE,
    error_code,
    latest_code,
    login,
    logout,
    request_code,
    set_cookie_headers,
    unique_email,
    verify,
)
from sqlalchemy import select, text

from ramus_api.main import create_app
from ramus_api.modules.access.domain.codes import SESSION_TTL
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.access.infrastructure.models import EmailCodeRow, SessionRow
from ramus_api.settings import Settings

pytestmark = pytest.mark.integration

SESSION_MAX_AGE = int(SESSION_TTL.total_seconds())


@pytest.fixture
def mailer() -> FakeMailer:
    return FakeMailer()


@pytest.fixture
def app(integration_settings: Settings, mailer: FakeMailer) -> FastAPI:
    return create_app(integration_settings, mailer=mailer)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as instance:
        yield instance


def cookie_attributes(header: str) -> dict[str, str]:
    name_value, *attributes = [part.strip() for part in header.split(";")]
    parsed = {"__name__": name_value.split("=", 1)[0]}
    for attribute in attributes:
        key, _, value = attribute.partition("=")
        parsed[key.lower()] = value
    return parsed


def session_cookie(response) -> dict[str, str]:
    [header] = [h for h in set_cookie_headers(response) if h.startswith(f"{SESSION_COOKIE}=")]
    return cookie_attributes(header)


# Cookie -----------------------------------------------------------------------------------------


def test_session_cookie_attributes(client: TestClient, mailer: FakeMailer) -> None:
    cookie = session_cookie(login(client, mailer, unique_email("cookie")))
    assert "httponly" in cookie
    assert cookie["samesite"].lower() == "lax"
    assert cookie["path"] == "/"
    assert SESSION_MAX_AGE - 5 <= int(cookie["max-age"]) <= SESSION_MAX_AGE
    assert cookie["expires"]
    assert "secure" not in cookie


def test_secure_cookie_when_configured(integration_settings: Settings) -> None:
    mailer = FakeMailer()
    settings = integration_settings.model_copy(update={"cookie_secure": True})
    with TestClient(create_app(settings, mailer=mailer)) as client:
        cookie = session_cookie(login_without_cookie_jar(client, mailer, unique_email("secure")))
    assert "secure" in cookie
    assert "httponly" in cookie


def login_without_cookie_jar(client: TestClient, mailer: FakeMailer, email: str):
    # Secure cookies are not stored for http://testserver, so only inspect the response header.
    assert request_code(client, email).status_code == 202
    response = verify(client, email, latest_code(mailer, email))
    assert response.status_code == 200
    return response


# Current account --------------------------------------------------------------------------------


def test_me_without_cookie_is_unauthorized(client: TestClient) -> None:
    response = client.get(ME_PATH)
    assert response.status_code == 401
    assert error_code(response) == "UNAUTHORIZED"
    assert response.json()["error"]["message"] == "로그인이 필요합니다."
    assert response.json()["error"]["details"] is None


def test_me_with_unknown_token_is_unauthorized(client: TestClient) -> None:
    client.cookies.set(SESSION_COOKIE, "not-a-real-session-token")
    assert client.get(ME_PATH).status_code == 401


def test_expired_session_is_unauthorized(client: TestClient, app: FastAPI, mailer: FakeMailer) -> None:
    me = login(client, mailer, unique_email("stale")).json()
    with app.state.container.database.transaction() as session:
        session.execute(
            text("UPDATE session SET expires_at = now() - interval '1 second' WHERE account_id = :a"),
            {"a": me["account"]["id"]},
        )
    response = client.get(ME_PATH)
    assert response.status_code == 401
    assert error_code(response) == "UNAUTHORIZED"


def test_me_reports_the_ai_connection_status(client: TestClient, app: FastAPI, mailer: FakeMailer) -> None:
    me = login(client, mailer, unique_email("ai")).json()
    with app.state.container.database.transaction() as session:
        session.execute(
            text(
                "INSERT INTO ai_connection (account_id, provider, ciphertext, status, verified_at) "
                "VALUES (:a, 'openai', 'opaque', 'invalid', now())"
            ),
            {"a": me["account"]["id"]},
        )
    assert client.get(ME_PATH).json()["ai_connection"] == {"status": "invalid"}


# Logout -----------------------------------------------------------------------------------------


def test_logout_revokes_the_session_and_clears_the_cookie(
    client: TestClient, app: FastAPI, mailer: FakeMailer
) -> None:
    login(client, mailer, unique_email("bye"))
    token = client.cookies.get(SESSION_COOKIE)
    assert client.get(ME_PATH).status_code == 200
    response = logout(client)
    assert response.status_code == 200
    assert response.json() == {}
    cleared = session_cookie(response)
    assert cleared["max-age"] == "0"
    assert cleared["path"] == "/"
    assert "httponly" in cleared
    assert cleared["samesite"].lower() == "lax"
    assert client.get(ME_PATH).status_code == 401

    # The revoked token stays unusable even if a client keeps sending it.
    client.cookies.set(SESSION_COOKIE, token)
    assert client.get(ME_PATH).status_code == 401
    assert logout(client).status_code == 200


def test_logout_without_cookie_is_ok(client: TestClient) -> None:
    response = logout(client)
    assert response.status_code == 200
    assert response.json() == {}


def test_logout_requires_the_idempotency_key_and_empty_body(client: TestClient) -> None:
    missing = client.post("/api/auth/logout", json={})
    assert missing.status_code == 400
    assert error_code(missing) == "IDEMPOTENCY_KEY_INVALID"
    extra = client.post("/api/auth/logout", json={"x": 1}, headers={"Idempotency-Key": "logout-extra"})
    assert extra.status_code == 422
    assert error_code(extra) == "INVALID_INPUT"


# Secrets ----------------------------------------------------------------------------------------


def text_columns(app: FastAPI) -> list[tuple[str, str]]:
    # Hex digests are excluded: a random 6-digit code can appear inside a SHA-256 hex string by chance.
    # They are checked separately against the plaintext.
    with app.state.container.database.transaction() as session:
        rows = session.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND data_type IN ('text', 'character varying', 'jsonb') "
                "AND table_name <> 'alembic_version' "
                "AND column_name NOT LIKE '%\\_hash' AND column_name <> 'fingerprint'"
            )
        ).all()
    return [(row.table_name, row.column_name) for row in rows]


def stored_values_containing(app: FastAPI, needle: str) -> list[str]:
    hits = []
    with app.state.container.database.transaction() as session:
        for table, column in text_columns(app):
            found = session.scalar(
                text(f'SELECT count(*) FROM "{table}" WHERE "{column}"::text LIKE :pattern'),
                {"pattern": f"%{needle}%"},
            )
            if found:
                hits.append(f"{table}.{column}")
    return hits


def test_codes_and_tokens_are_stored_only_as_hashes(
    client: TestClient, app: FastAPI, mailer: FakeMailer, caplog: pytest.LogCaptureFixture
) -> None:
    email = unique_email("secret")
    with caplog.at_level(logging.DEBUG):
        me = login(client, mailer, email).json()
    code = latest_code(mailer, email)
    token = client.cookies.get(SESSION_COOKIE)
    assert token
    with app.state.container.database.transaction() as session:
        code_row = session.scalars(select(EmailCodeRow).where(EmailCodeRow.email == email)).one()
        session_row = session.scalars(
            select(SessionRow).where(SessionRow.account_id == me["account"]["id"])
        ).one()
    assert code not in code_row.code_hash
    assert session_row.token_hash != token
    assert stored_values_containing(app, code) == []
    assert stored_values_containing(app, token) == []
    assert token not in caplog.text


def test_failing_mailer_is_a_server_error_without_leaking_the_code(
    integration_settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    class BrokenMailer:
        def __init__(self) -> None:
            self.codes: list[str] = []

        async def send_code(self, email: str, code: str) -> None:
            self.codes.append(code)
            raise RuntimeError("mail transport unavailable")

    broken = BrokenMailer()
    with TestClient(create_app(integration_settings, mailer=broken), raise_server_exceptions=False) as client:
        with caplog.at_level(logging.DEBUG):
            response = request_code(client, unique_email("broken"))
    assert response.status_code == 503
    assert error_code(response) == "SERVICE_UNAVAILABLE"
    [code] = broken.codes
    assert code not in response.text
    assert code not in caplog.text
