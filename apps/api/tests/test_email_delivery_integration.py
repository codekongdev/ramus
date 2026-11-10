"""Email delivery retries use temporary PostgreSQL data and a gated in-memory transport."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from itertools import count
from threading import Event, Lock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from login_flow import error_code, new_key, request_code, unique_email, verify
from sqlalchemy import select, text, update

from ramus_api.main import create_app
from ramus_api.modules.access.application.rate_limits import REQUEST_EMAIL_LIMIT
from ramus_api.modules.access.domain.codes import hash_code
from ramus_api.modules.access.fakes.services import CodeDelivery
from ramus_api.modules.access.infrastructure.models import EmailCodeRow
from ramus_api.modules.access.infrastructure.system import SystemSecretSource
from ramus_api.settings import Settings
from ramus_api.shared.infrastructure.receipts import RequestReceiptRow

pytestmark = pytest.mark.integration
PROVIDER_DETAIL = "provider-private-delivery-detail"


class ControlledMailer:
    """Records synthetic attempts; selected calls fail or wait without sending any mail."""

    def __init__(self) -> None:
        self.fail_calls: set[int] = set()
        self.pause_call: int | None = None
        self.entered, self.release = Event(), Event()
        self.before_send: Callable[[], None] | None = None
        self._lock = Lock()
        self._attempts: list[CodeDelivery] = []

    @property
    def attempts(self) -> tuple[CodeDelivery, ...]:
        with self._lock:
            return tuple(self._attempts)

    async def send_code(self, email: str, code: str) -> None:
        with self._lock:
            self._attempts.append(CodeDelivery(email, code))
            ordinal = len(self._attempts)
        if self.before_send is not None:
            self.before_send()
        if ordinal == self.pause_call:
            self.entered.set()
            if not await asyncio.to_thread(self.release.wait, 30):
                raise AssertionError("The test did not release its mail delivery gate")
        if ordinal in self.fail_calls:
            raise RuntimeError(f"{PROVIDER_DETAIL}:{code}")


@pytest.fixture
def mailer() -> ControlledMailer:
    return ControlledMailer()


@pytest.fixture
def app(integration_settings: Settings, mailer: ControlledMailer, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    # Distinct deterministic values avoid random-code collision skips in replacement checks.
    sequence = count(671001)
    monkeypatch.setattr(SystemSecretSource, "new_code", lambda _self: f"{next(sequence):06d}")
    return create_app(integration_settings, mailer=mailer)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, client=(f"delivery-{uuid4().hex}", 50000), raise_server_exceptions=False) as instance:
        yield instance


def codes(app: FastAPI, email: str) -> list[EmailCodeRow]:
    with app.state.container.database.transaction() as session:
        return list(session.scalars(select(EmailCodeRow).where(EmailCodeRow.email == email)
                                    .order_by(EmailCodeRow.created_at, EmailCodeRow.id)))


def deliveries(app: FastAPI, email: str) -> list[dict]:
    with app.state.container.database.transaction() as session:
        return [dict(row) for row in session.execute(text(
            "SELECT * FROM email_code_delivery WHERE email = :email ORDER BY created_at, id"
        ), {"email": email}).mappings()]


def age_confirmed_code(app: FastAPI, email: str) -> None:
    with app.state.container.database.transaction() as session:
        session.execute(update(EmailCodeRow).where(EmailCodeRow.email == email)
                        .values(created_at=EmailCodeRow.created_at - timedelta(seconds=61)))


def assert_matches_code(app: FastAPI, row: EmailCodeRow, code: str) -> None:
    secret = app.state.container.settings.auth_secret.get_secret_value()
    assert row.code_hash == hash_code(code, str(row.id), secret)


@pytest.mark.parametrize("reuse_key", [True, False], ids=["same-key", "new-key"])
def test_failed_initial_delivery_can_retry_immediately_and_replay_sends_nothing(
    client: TestClient, app: FastAPI, mailer: ControlledMailer, reuse_key: bool
) -> None:
    email, original_key = unique_email("recover-delivery"), new_key("delivery")
    mailer.fail_calls = {1}
    failed = request_code(client, email, original_key)
    assert failed.status_code == 503
    assert error_code(failed) == "SERVICE_UNAVAILABLE"
    assert codes(app, email) == []
    assert [row["status"] for row in deliveries(app, email)] == ["failed"]
    assert error_code(verify(client, email, mailer.attempts[0].code)) == "AUTH_CODE_EXPIRED"

    successful_key = original_key if reuse_key else new_key("recovery")
    recovered = request_code(client, email, successful_key)
    replay = request_code(client, f"  {email.upper()}  ", successful_key)
    assert recovered.status_code == replay.status_code == 202
    assert recovered.json() == replay.json()
    assert len(mailer.attempts) == 2
    assert mailer.attempts[0].code != mailer.attempts[1].code
    [active] = codes(app, email)
    assert_matches_code(app, active, mailer.attempts[1].code)
    assert error_code(verify(client, email, mailer.attempts[0].code)) == "AUTH_CODE_INVALID"
    assert verify(client, email, mailer.attempts[1].code).status_code == 200
    if not reuse_key:
        expired_action = request_code(client, email, original_key)
        assert expired_action.status_code == 422
        assert error_code(expired_action) == "AUTH_CODE_EXPIRED"
        assert len(mailer.attempts) == 2


@pytest.mark.parametrize("first_failed", [True, False], ids=["failed", "sent"])
def test_a_delivery_receipt_key_cannot_be_reused_for_another_email(
    client: TestClient, mailer: ControlledMailer, first_failed: bool
) -> None:
    headers = new_key("delivery-conflict")
    if first_failed:
        mailer.fail_calls = {1}
    first = request_code(client, unique_email("first-recipient"), headers)
    assert first.status_code == (503 if first_failed else 202)
    conflict = request_code(client, unique_email("different-recipient"), headers)
    assert conflict.status_code == 409
    assert error_code(conflict) == "IDEMPOTENCY_CONFLICT"
    assert len(mailer.attempts) == 1


@pytest.mark.parametrize("same_key", [True, False], ids=["same-key", "same-email"])
def test_live_delivery_lease_rejects_concurrent_requests_without_sending_twice(
    client: TestClient, mailer: ControlledMailer, same_key: bool
) -> None:
    email, original_key = unique_email("concurrent-delivery"), new_key("inflight")
    competing_key = original_key if same_key else new_key("competing")
    mailer.pause_call = 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(request_code, client, email, original_key)
        try:
            assert mailer.entered.wait(10), "The initial delivery never reached the mailer"
            second = pool.submit(request_code, client, email, competing_key).result(timeout=10)
            assert second.status_code == 503
            assert error_code(second) == "SERVICE_UNAVAILABLE"
            assert len(mailer.attempts) == 1
        finally:
            mailer.release.set()
        delivered = first.result(timeout=10)
    assert delivered.status_code == 202
    replay = request_code(client, email, original_key)
    assert replay.status_code == 202
    assert replay.json() == delivered.json()
    assert len(mailer.attempts) == 1


def test_mailer_runs_without_a_database_transaction_and_code_activates_only_after_success(
    client: TestClient, app: FastAPI, mailer: ControlledMailer
) -> None:
    email = unique_email("activate-after-mail")
    checked_out: list[int] = []
    mailer.before_send = lambda: checked_out.append(app.state.container.database.engine.pool.checkedout())
    mailer.pause_call = 1
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(request_code, client, email)
        try:
            assert mailer.entered.wait(10), "The delivery never reached the mailer"
            assert checked_out == [0]
            assert codes(app, email) == []
            [attempt] = deliveries(app, email)
            assert attempt["status"] == "sending"
            assert attempt["lease_until"] is not None
            assert error_code(verify(client, email, mailer.attempts[0].code)) == "AUTH_CODE_EXPIRED"
        finally:
            mailer.release.set()
        response = pending.result(timeout=10)
    assert response.status_code == 202
    [active] = codes(app, email)
    assert_matches_code(app, active, mailer.attempts[0].code)
    [sent] = deliveries(app, email)
    assert sent["status"] == "sent" and sent["sent_at"] is not None
    assert verify(client, email, mailer.attempts[0].code).status_code == 200


@pytest.mark.parametrize("resend_fails", [True, False], ids=["failed-resend", "successful-resend"])
def test_previous_confirmed_code_is_preserved_until_replacement_is_successful(
    client: TestClient, app: FastAPI, mailer: ControlledMailer, resend_fails: bool
) -> None:
    email = unique_email("preserve-code")
    assert request_code(client, email).status_code == 202
    old_code = mailer.attempts[0].code
    [old_row] = codes(app, email)
    age_confirmed_code(app, email)
    mailer.pause_call = 2
    if resend_fails:
        mailer.fail_calls = {2}
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(request_code, client, email)
        try:
            assert mailer.entered.wait(10), "The replacement delivery never reached the mailer"
            [while_sending] = codes(app, email)
            assert while_sending.id == old_row.id
            assert_matches_code(app, while_sending, old_code)
        finally:
            mailer.release.set()
        response = pending.result(timeout=10)
    if resend_fails:
        assert response.status_code == 503
        [still_active] = codes(app, email)
        assert still_active.id == old_row.id
        assert verify(client, email, old_code).status_code == 200
    else:
        assert response.status_code == 202
        assert error_code(verify(client, email, old_code)) == "AUTH_CODE_INVALID"
        assert verify(client, email, mailer.attempts[1].code).status_code == 200


def test_previous_code_can_be_verified_while_a_replacement_mail_is_in_flight(
    client: TestClient, app: FastAPI, mailer: ControlledMailer
) -> None:
    email = unique_email("verify-during-mail")
    assert request_code(client, email).status_code == 202
    age_confirmed_code(app, email)
    mailer.pause_call = 2
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(request_code, client, email)
        try:
            assert mailer.entered.wait(10), "The replacement delivery never reached the mailer"
            assert verify(client, email, mailer.attempts[0].code).status_code == 200
        finally:
            mailer.release.set()
        response = pending.result(timeout=10)
    assert response.status_code == 202
    assert verify(client, email, mailer.attempts[1].code).status_code == 200


def test_immediate_failure_retries_still_obey_the_hourly_request_budget(
    client: TestClient, mailer: ControlledMailer
) -> None:
    email = unique_email("failed-mail-budget")
    mailer.fail_calls = set(range(1, REQUEST_EMAIL_LIMIT + 2))
    for _ in range(REQUEST_EMAIL_LIMIT):
        response = request_code(client, email)
        assert response.status_code == 503
        assert error_code(response) == "SERVICE_UNAVAILABLE"
    limited = request_code(client, email)
    assert limited.status_code == 429
    assert error_code(limited) == "AUTH_RATE_LIMITED"
    assert len(mailer.attempts) == REQUEST_EMAIL_LIMIT


@pytest.mark.parametrize("old_attempt_fails", [True, False], ids=["late-failure", "late-success"])
def test_expired_delivery_lease_is_reclaimed_and_late_completion_cannot_replace_the_new_code(
    client: TestClient, app: FastAPI, mailer: ControlledMailer, old_attempt_fails: bool
) -> None:
    email, headers = unique_email("reclaim-mail"), new_key("reclaim")
    mailer.pause_call = 1
    if old_attempt_fails:
        mailer.fail_calls = {1}
    with ThreadPoolExecutor(max_workers=1) as pool:
        abandoned = pool.submit(request_code, client, email, headers)
        try:
            assert mailer.entered.wait(10), "The abandoned delivery never reached the mailer"
            [original] = deliveries(app, email)
            with app.state.container.database.transaction() as session:
                changed = session.execute(text(
                    "UPDATE email_code_delivery SET lease_until = now() - interval '1 second' "
                    "WHERE id = :id AND status = 'sending'"
                ), {"id": original["id"]})
                assert changed.rowcount == 1
            recovered = request_code(client, email, headers)
            assert recovered.status_code == 202
            [current] = deliveries(app, email)
            assert current["id"] == original["id"]
            assert current["attempt_id"] != original["attempt_id"]
            assert current["code_id"] != original["code_id"]
            assert current["status"] == "sent"
            [active] = codes(app, email)
            assert_matches_code(app, active, mailer.attempts[1].code)
        finally:
            mailer.release.set()
        stale = abandoned.result(timeout=10)
    assert stale.status_code == 503
    assert error_code(stale) == "SERVICE_UNAVAILABLE"
    assert len(mailer.attempts) == 2
    [still_active] = codes(app, email)
    assert still_active.id == active.id
    assert_matches_code(app, still_active, mailer.attempts[1].code)
    replay = request_code(client, email, headers)
    assert replay.status_code == 202
    assert replay.json() == recovered.json()
    assert len(mailer.attempts) == 2
    assert error_code(verify(client, email, mailer.attempts[0].code)) == "AUTH_CODE_INVALID"
    assert verify(client, email, mailer.attempts[1].code).status_code == 200


def test_raw_codes_and_provider_exceptions_never_enter_receipts_responses_or_logs(
    client: TestClient, app: FastAPI, mailer: ControlledMailer, caplog: pytest.LogCaptureFixture
) -> None:
    email, headers = unique_email("private-mail"), new_key("private")
    mailer.fail_calls = {1}
    failed = request_code(client, email, headers)
    recovered = request_code(client, email, headers)
    assert failed.status_code == 503 and recovered.status_code == 202
    values = [delivery.code for delivery in mailer.attempts]
    with app.state.container.database.transaction() as session:
        receipt = session.scalar(select(RequestReceiptRow).where(
            RequestReceiptRow.scope == "auth.email_code",
            RequestReceiptRow.idempotency_key == headers["Idempotency-Key"],
        ))
        assert receipt is not None
        assert set(receipt.response) == {"delivery_id"}
        stored_values = [value for row in session.execute(text(
            "SELECT to_jsonb(d) FROM email_code_delivery d WHERE email = :email "
            "UNION ALL SELECT to_jsonb(c) FROM email_code c WHERE email = :email"
        ), {"email": email}) for value in row]
        stored_values.append(receipt.response)
    for value in values:
        assert value not in failed.text and value not in recovered.text
        assert value not in caplog.text
    assert PROVIDER_DETAIL not in failed.text and PROVIDER_DETAIL not in recovered.text
    assert PROVIDER_DETAIL not in caplog.text
    for record in stored_values:
        assert all(value not in record.values() for value in values)
        assert PROVIDER_DETAIL not in str(record)
