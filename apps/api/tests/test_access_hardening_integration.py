"""A1 regressions: boundary validation, limits across challenges, and bounded receipt replay."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from login_flow import error_code, latest_code, new_key, request_code, unique_email, verify
from sqlalchemy import event, func, select, update

from ramus_api.main import create_app
from ramus_api.modules.access.application.rate_limits import (
    REQUEST_EMAIL_LIMIT,
    REQUEST_IP_LIMIT,
    SESSION_REISSUE_LIMIT,
    VERIFY_EMAIL_LIMIT,
    VERIFY_IP_LIMIT,
)
from ramus_api.modules.access.domain.codes import hash_code
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.access.infrastructure.models import AuthAttemptRow, EmailCodeRow, SessionRow
from ramus_api.settings import Settings
from ramus_api.shared.domain import fingerprint, new_id, utc_now
from ramus_api.shared.infrastructure.receipts import RequestReceiptRow

pytestmark = pytest.mark.integration


@pytest.fixture
def mailer() -> FakeMailer:
    return FakeMailer()


@pytest.fixture
def app(integration_settings: Settings, mailer: FakeMailer) -> FastAPI:
    return create_app(integration_settings, mailer=mailer)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # Each case has its own network peer. The database's other test accounts remain untouched.
    with TestClient(app, client=(f"peer-{uuid4().hex}", 50000)) as instance:
        yield instance


def seed_attempts(app: FastAPI, scope: str, subject: str, count: int) -> None:
    secret = app.state.container.settings.auth_secret.get_secret_value()
    with app.state.container.database.transaction() as transaction:
        transaction.add_all(
            [
                AuthAttemptRow(
                    id=new_id(),
                    scope=scope,
                    subject_hash=hash_code(subject, scope, secret),
                    created_at=utc_now(),
                )
                for _ in range(count)
            ]
        )


@pytest.mark.parametrize(
    "email", ["a\x00@example.test", "a\x1b@example.test", "a\u200b@example.test", "İ" * 125 + "@x.co"]
)
def test_invalid_email_is_422_without_attempt_or_delivery(
    client: TestClient, mailer: FakeMailer, email: str
) -> None:
    response = request_code(client, email)
    assert response.status_code == 422
    assert error_code(response) == "INVALID_INPUT"
    assert not mailer.deliveries


def test_code_requires_six_ascii_digits(client: TestClient) -> None:
    response = verify(client, unique_email(), "１２３４５６")
    assert response.status_code == 422
    assert error_code(response) == "INVALID_INPUT"


def test_email_request_budget_survives_code_replacement(client: TestClient, app: FastAPI) -> None:
    email = unique_email("hourly-request")
    for _ in range(REQUEST_EMAIL_LIMIT):
        assert request_code(client, email).status_code == 202
        # Move only the 60-second challenge cooldown; the hourly request history stays intact.
        with app.state.container.database.transaction() as transaction:
            transaction.execute(
                update(EmailCodeRow)
                .where(EmailCodeRow.email == email)
                .values(created_at=EmailCodeRow.created_at - timedelta(seconds=61))
            )
    response = request_code(client, email)
    assert response.status_code == 429
    assert error_code(response) == "AUTH_RATE_LIMITED"
    assert "resend_available_at" in response.json()["error"]["details"]


def test_verification_email_budget_and_rolling_expiry(client: TestClient, app: FastAPI) -> None:
    email = unique_email("hourly-verify")
    seed_attempts(app, "verify", f"email:{email}", VERIFY_EMAIL_LIMIT - 1)
    assert error_code(verify(client, email, "000000")) == "AUTH_CODE_EXPIRED"
    assert error_code(verify(client, email, "000000")) == "AUTH_RATE_LIMITED"
    secret = app.state.container.settings.auth_secret.get_secret_value()
    with app.state.container.database.transaction() as transaction:
        transaction.execute(
            update(AuthAttemptRow)
            .where(AuthAttemptRow.subject_hash == hash_code(f"email:{email}", "verify", secret))
            .values(created_at=utc_now() - timedelta(hours=1, seconds=1))
        )
    assert error_code(verify(client, email, "000000")) == "AUTH_CODE_EXPIRED"


@pytest.mark.parametrize("scope,limit", [("request", REQUEST_IP_LIMIT), ("verify", VERIFY_IP_LIMIT)])
def test_ip_budget_applies_across_emails_and_ignores_forwarded_header(
    app: FastAPI, scope: str, limit: int
) -> None:
    peer = f"ip-{uuid4().hex}"
    seed_attempts(app, scope, f"ip:{peer}", limit)
    with TestClient(app, client=(peer, 50000)) as client:
        for _ in range(2):
            headers = {**new_key(), "X-Forwarded-For": f"bypass-{uuid4().hex}"}
            email = unique_email()
            response = (
                request_code(client, email, headers)
                if scope == "request"
                else verify(client, email, "000000", headers)
            )
            assert response.status_code == 429
            assert error_code(response) == "AUTH_RATE_LIMITED"


def test_hmac_protects_challenge_and_receipt_from_code_enumeration(
    client: TestClient, app: FastAPI, mailer: FakeMailer
) -> None:
    email = unique_email("hmac")
    assert request_code(client, email).status_code == 202
    code = latest_code(mailer, email)
    headers = new_key("hmac-verify")
    assert verify(client, email, code, headers).status_code == 200
    with app.state.container.database.transaction() as transaction:
        challenge = transaction.scalar(select(EmailCodeRow).where(EmailCodeRow.email == email))
        receipt = transaction.scalar(
            select(RequestReceiptRow).where(
                RequestReceiptRow.scope == "auth.verify",
                RequestReceiptRow.idempotency_key == headers["Idempotency-Key"],
            )
        )
        assert challenge.code_hash != hash_code(code, str(challenge.id))
        assert receipt.fingerprint != fingerprint({"email": email, "code": code})
        assert code not in str(receipt.response)


def test_concurrent_verify_replays_issue_at_most_three_sessions(
    client: TestClient, app: FastAPI, mailer: FakeMailer
) -> None:
    email = unique_email("bounded-replay")
    assert request_code(client, email).status_code == 202
    code, headers = latest_code(mailer, email), new_key("bounded")
    # The first request establishes the receipt before concurrent transport retries arrive.
    first = verify(client, email, code, headers)
    assert first.status_code == 200
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(lambda _: verify(client, email, code, headers), range(6)))
    assert sum(response.status_code == 200 for response in responses) == SESSION_REISSUE_LIMIT - 1
    assert sum(response.status_code == 429 for response in responses) == 7 - SESSION_REISSUE_LIMIT
    with app.state.container.database.transaction() as transaction:
        count = transaction.scalar(
            select(func.count())
            .select_from(SessionRow)
            .where(SessionRow.account_id == first.json()["account"]["id"])
        )
    assert count == SESSION_REISSUE_LIMIT


def test_me_reads_session_and_profile_in_one_transaction(
    client: TestClient, app: FastAPI, mailer: FakeMailer
) -> None:
    email = unique_email("atomic-profile")
    assert request_code(client, email).status_code == 202
    assert verify(client, email, latest_code(mailer, email)).status_code == 200
    transactions: list[object] = []
    engine = app.state.container.database.engine

    def began(connection) -> None:
        transactions.append(connection)

    event.listen(engine, "begin", began)
    try:
        assert client.get("/api/me").status_code == 200
    finally:
        event.remove(engine, "begin", began)
    assert len(transactions) == 1


def test_me_returns_401_when_the_account_disappears_during_authentication(
    client: TestClient, mailer: FakeMailer, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ramus_api.modules.access.infrastructure.stores import SqlAccountStore

    email = unique_email("deleted-profile")
    assert request_code(client, email).status_code == 202
    assert verify(client, email, latest_code(mailer, email)).status_code == 200
    monkeypatch.setattr(SqlAccountStore, "get_profile", lambda *args: None)
    response = client.get("/api/me")
    assert response.status_code == 401
    assert error_code(response) == "UNAUTHORIZED"
