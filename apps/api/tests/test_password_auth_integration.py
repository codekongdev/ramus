"""Default signup/login against disposable PostgreSQL, with no mail or model calls."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from login_flow import TEST_PASSWORD, error_code, new_key, unique_email
from sqlalchemy import func, select

from ramus_api.main import create_app
from ramus_api.modules.access.domain.codes import hash_code
from ramus_api.modules.access.infrastructure.models import AccountRow, AuthAttemptRow
from ramus_api.settings import Settings
from ramus_api.shared.domain import new_id, utc_now
from ramus_api.shared.infrastructure.receipts import RequestReceiptRow

pytestmark = pytest.mark.integration


@pytest.fixture
def rig(integration_settings):
    app = create_app(integration_settings.model_copy(update={"email_code_auth_enabled": False}))
    client = TestClient(app, client=(f"password-{uuid4().hex}", 50000))
    try:
        yield app, client
    finally:
        client.close()
        app.state.container.database.dispose()


def register(client, email, password=TEST_PASSWORD, key=None):
    return client.post("/api/auth/register", json={"email": email, "password": password, "display_name": "테스트 닉네임"}, headers=key or new_key())


def sign_in(client, email, password=TEST_PASSWORD, key=None):
    return client.post("/api/auth/login", json={"email": email, "password": password}, headers=key or new_key())


def test_registration_login_and_mail_free_default(rig, caplog):
    app, client = rig
    email = unique_email("password")
    response = register(client, email)
    assert response.status_code == 200, response.text
    me = response.json()
    assert me["account"]["display_name"] == "테스트 닉네임"
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/api/me").json() == me
    assert client.post("/api/auth/logout", json={}, headers=new_key()).status_code == 200
    assert client.get("/api/me").status_code == 401
    logged_in = sign_in(client, f" {email.upper()} ")
    assert logged_in.status_code == 200 and logged_in.json() == me
    assert client.post("/api/auth/email-code", json={"email": email}, headers=new_key()).status_code == 410
    assert client.post("/api/auth/verify", json={"email": email, "code": "123456"}, headers=new_key()).status_code == 410
    with app.state.container.database.transaction() as session:
        account = session.get(AccountRow, UUID(me["account"]["id"]))
        assert account.password_hash.startswith("scrypt$")
        assert TEST_PASSWORD not in account.password_hash
        receipts = session.scalars(select(RequestReceiptRow)).all()
        assert all(TEST_PASSWORD not in str(row.response) for row in receipts)
    assert TEST_PASSWORD not in response.text and TEST_PASSWORD not in caplog.text


def test_duplicate_and_legacy_accounts_cannot_be_taken_over(rig):
    app, client = rig
    email = unique_email("duplicate")
    assert register(client, email).status_code == 200
    assert register(client, email).status_code == 409
    legacy = unique_email("legacy")
    with app.state.container.database.transaction() as session:
        session.add(AccountRow(id=new_id(), email=legacy, display_name="기존 계정"))
    assert register(client, legacy).status_code == 409
    assert sign_in(client, legacy).status_code == 401
    assert sign_in(client, unique_email("missing")).json() == sign_in(client, email, "wrong-password").json()


def test_signup_and_login_receipt_retries_preserve_account_and_bound_sessions(rig):
    _, client = rig
    email, key = unique_email("replay"), new_key()
    first = register(client, email, key=key)
    assert first.status_code == 200
    for _ in range(2):
        assert register(client, email, key=key).json() == first.json()
    assert register(client, email, key=key).status_code == 429
    assert register(client, email, "another-password", key=key).status_code == 409
    login_key = new_key()
    assert sign_in(client, email, key=login_key).status_code == 200
    assert sign_in(client, email, key=login_key).status_code == 200
    assert sign_in(client, email, "incorrect-password", key=login_key).status_code == 401


def test_parallel_signup_creates_one_account_and_does_not_overwrite_password(rig):
    app, _ = rig
    email = unique_email("parallel")

    def signup(index):
        client = TestClient(app, client=(f"parallel-{uuid4().hex}", 50000))
        try:
            return register(client, email, f"parallel-password-{index}")
        finally:
            client.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(signup, range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    with app.state.container.database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(AccountRow).where(AccountRow.email == email)) == 1


@pytest.mark.parametrize("subject", ["email", "ip"])
def test_password_rate_limits_do_not_trust_forwarded_header(rig, subject):
    app, client = rig
    email = unique_email("limited")
    value = email if subject == "email" else client._transport.client[0]
    digest = hash_code(f"{subject}:{value}", "password_login", app.state.container.settings.auth_secret.get_secret_value())
    with app.state.container.database.transaction() as session:
        session.add_all([AuthAttemptRow(id=new_id(), scope="password_login", subject_hash=digest, created_at=utc_now())
                         for _ in range(30 if subject == "email" else 300)])
    response = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD},
                           headers={**new_key(), "X-Forwarded-For": "bypass"})
    assert response.status_code == 429 and error_code(response) == "AUTH_RATE_LIMITED"


def test_production_password_auth_starts_without_smtp():
    settings = Settings(_env_file=None, database_url="postgresql+psycopg://nobody:nothing@127.0.0.1:1/nowhere",
                        RAMUS_ENV="production", RAMUS_AUTH_SECRET="s" * 32)
    app = create_app(settings)
    client = TestClient(app)
    try:
        assert client.get("/api/health").status_code == 200
    finally:
        client.close()
        app.state.container.database.dispose()
