"""Downgrade cannot leave a successful setup receipt after dropping its password hash."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from login_flow import TEST_PASSWORD, legacy_login, new_key, unique_email
from sqlalchemy import select

from ramus_api.main import create_app
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.access.infrastructure.models import AccountRow
from ramus_api.settings import Settings
from ramus_api.shared.infrastructure.receipts import RequestReceiptRow

pytestmark = pytest.mark.integration


def test_password_downgrade_removes_setup_receipts_before_reupgrade(fresh_database_url, run_alembic):
    run_alembic(fresh_database_url, "upgrade", "head")
    settings = Settings(_env_file=None, database_url=fresh_database_url, RAMUS_EMAIL_CODE_AUTH_ENABLED=True)
    mailer = FakeMailer()
    app = create_app(settings, mailer=mailer)
    key = new_key("setup-downgrade")
    client = TestClient(app, client=(f"migration-{uuid4().hex}", 50000))
    try:
        identity = legacy_login(client, mailer, unique_email("migration-legacy")).json()
        token = client.cookies.get("ramus_session")
        account_id = UUID(identity["account"]["id"])
        assert client.put("/api/me/password", json={"password": TEST_PASSWORD}, headers=key).status_code == 200
    finally:
        client.close()
        app.state.container.database.dispose()
    run_alembic(fresh_database_url, "downgrade", "d65a18c9f203")
    run_alembic(fresh_database_url, "upgrade", "head")
    restored = create_app(settings, mailer=mailer)
    retry = TestClient(restored)
    retry.cookies.set("ramus_session", token)
    try:
        with restored.state.container.database.transaction() as transaction:
            assert transaction.get(AccountRow, account_id).password_hash is None
            assert transaction.scalar(select(RequestReceiptRow).where(
                RequestReceiptRow.idempotency_key == key["Idempotency-Key"],
            )) is None
        assert retry.get("/api/me/password").json() == {"configured": False}
        assert retry.put("/api/me/password", json={"password": TEST_PASSWORD}, headers=key).status_code == 200
        with restored.state.container.database.transaction() as transaction:
            assert transaction.get(AccountRow, account_id).password_hash is not None
    finally:
        retry.close()
        restored.state.container.database.dispose()
