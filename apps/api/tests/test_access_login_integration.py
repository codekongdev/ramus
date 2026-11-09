"""Email-code login against a real (temporary) PostgreSQL database."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from login_flow import (
    ME_PATH,
    error_code,
    latest_code,
    login,
    new_key,
    request_code,
    unique_email,
    verify,
    wrong_code,
)
from sqlalchemy import create_engine, func, select, text

from ramus_api.main import create_app
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.access.infrastructure.models import AccountRow, EmailCodeRow, MembershipRow
from ramus_api.modules.projects.infrastructure.models import ProjectRow
from ramus_api.modules.projects.infrastructure.sample import SHARED_SAMPLE_PROJECT_ID
from ramus_api.settings import Settings

pytestmark = pytest.mark.integration


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


@pytest.fixture
def migrated_fresh_url(fresh_database_url: str, run_alembic) -> str:
    """An isolated migrated database with no seed, so row counts are exact."""
    run_alembic(fresh_database_url, "upgrade", "head")
    return fresh_database_url


def execute(app: FastAPI, sql: str, **params) -> None:
    with app.state.container.database.transaction() as session:
        session.execute(text(sql), params)


def latest_code_row(app: FastAPI, email: str) -> EmailCodeRow:
    with app.state.container.database.transaction() as session:
        statement = (
            select(EmailCodeRow).where(EmailCodeRow.email == email).order_by(EmailCodeRow.created_at.desc())
        )
        return session.scalars(statement).first()


def age_latest_code(app: FastAPI, email: str, seconds: int) -> None:
    execute(
        app,
        "UPDATE email_code SET created_at = created_at - make_interval(secs => :seconds) WHERE email = :email",
        seconds=seconds,
        email=email,
    )


def count_rows(url: str) -> tuple[int, int]:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            projects = connection.scalar(select(func.count()).select_from(ProjectRow))
            memberships = connection.scalar(
                select(func.count())
                .select_from(MembershipRow)
                .where(MembershipRow.project_id == SHARED_SAMPLE_PROJECT_ID)
            )
            return projects, memberships
    finally:
        engine.dispose()


# ON-AC-01 ---------------------------------------------------------------------------------------


def test_three_accounts_join_the_same_shared_project(migrated_fresh_url: str) -> None:
    mailer = FakeMailer()
    app = create_app(Settings(_env_file=None, database_url=migrated_fresh_url), mailer=mailer)
    emails = [unique_email(name) for name in ("ana", "ben", "cho")]
    with ExitStack() as stack:
        clients = [stack.enter_context(TestClient(app)) for _ in emails]
        verified = [login(c, mailer, email).json() for c, email in zip(clients, emails, strict=True)]
        assert {me["default_project_id"] for me in verified} == {str(SHARED_SAMPLE_PROJECT_ID)}
        for client, email, me in zip(clients, emails, verified, strict=True):
            current = client.get(ME_PATH)
            assert current.status_code == 200
            assert current.json() == me
            assert current.json()["account"]["email"] == email
            assert current.json()["account"]["display_name"] == email.split("@")[0]
            assert current.json()["ai_connection"] == {"status": "none"}
    assert len({me["account"]["id"] for me in verified}) == 3
    assert count_rows(migrated_fresh_url) == (1, 3)


def test_concurrent_first_logins_create_one_project_and_one_membership_each(migrated_fresh_url: str) -> None:
    # ON-AC-11: no seed command ran; racing logins must still create the shared project only once.
    mailer = FakeMailer()
    app = create_app(Settings(_env_file=None, database_url=migrated_fresh_url), mailer=mailer)
    emails = [unique_email(f"racer{n}") for n in range(6)]
    with ExitStack() as stack:
        clients = [stack.enter_context(TestClient(app)) for _ in emails]
        for client, email in zip(clients, emails, strict=True):
            assert request_code(client, email).status_code == 202
        jobs = [(c, e, latest_code(mailer, e)) for c, e in zip(clients, emails, strict=True)]
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            responses = list(pool.map(lambda job: verify(*job), jobs))
    assert [r.status_code for r in responses] == [200] * len(emails)
    assert {r.json()["default_project_id"] for r in responses} == {str(SHARED_SAMPLE_PROJECT_ID)}
    assert count_rows(migrated_fresh_url) == (1, len(emails))


def test_relogin_with_different_case_and_spaces_reuses_the_account(
    client: TestClient, app: FastAPI, mailer: FakeMailer
) -> None:
    email = unique_email("again")
    first = login(client, mailer, email).json()
    age_latest_code(app, email, 61)
    second = login(client, mailer, f"  {email.upper()}  ").json()
    assert second["account"] == first["account"]
    with app.state.container.database.transaction() as session:
        accounts = session.scalars(select(AccountRow).where(AccountRow.email == email)).all()
        memberships = session.scalars(
            select(MembershipRow).where(MembershipRow.account_id == accounts[0].id)
        ).all()
    assert len(accounts) == 1
    assert [(m.project_id, m.role) for m in memberships] == [(SHARED_SAMPLE_PROJECT_ID, "editor")]


# Code checks ------------------------------------------------------------------------------------


def test_malformed_email_is_invalid_input(client: TestClient, mailer: FakeMailer) -> None:
    response = request_code(client, "not-an-email")
    assert response.status_code == 422
    assert error_code(response) == "INVALID_INPUT"
    assert "not-an-email" not in response.text
    assert mailer.deliveries == ()


def test_wrong_code_is_rejected(client: TestClient, mailer: FakeMailer) -> None:
    email = unique_email("wrong")
    request_code(client, email)
    response = verify(client, email, wrong_code(latest_code(mailer, email)))
    assert response.status_code == 422
    assert error_code(response) == "AUTH_CODE_INVALID"
    assert response.json()["error"]["message"] == "인증 코드가 올바르지 않습니다. 다시 확인해 주세요."
    assert "set-cookie" not in response.headers


def test_five_wrong_attempts_exhaust_the_code(client: TestClient, mailer: FakeMailer) -> None:
    email = unique_email("exhaust")
    request_code(client, email)
    code = latest_code(mailer, email)
    for _ in range(5):
        assert error_code(verify(client, email, wrong_code(code))) == "AUTH_CODE_INVALID"
    response = verify(client, email, code)
    assert response.status_code == 422
    assert error_code(response) == "AUTH_CODE_EXPIRED"


def test_expired_code_is_rejected(client: TestClient, app: FastAPI, mailer: FakeMailer) -> None:
    email = unique_email("expired")
    request_code(client, email)
    execute(app, "UPDATE email_code SET expires_at = now() - interval '1 second' WHERE email = :e", e=email)
    response = verify(client, email, latest_code(mailer, email))
    assert response.status_code == 422
    assert error_code(response) == "AUTH_CODE_EXPIRED"
    assert response.json()["error"]["message"] == "인증 코드가 만료되었습니다. 코드를 다시 요청해 주세요."


def test_used_code_cannot_be_reused_with_a_new_key(client: TestClient, mailer: FakeMailer) -> None:
    email = unique_email("reuse")
    login(client, mailer, email)
    response = verify(client, email, latest_code(mailer, email))
    assert response.status_code == 422
    assert error_code(response) == "AUTH_CODE_EXPIRED"


def test_unknown_email_is_expired(client: TestClient) -> None:
    response = verify(client, unique_email("nobody"), "123456")
    assert error_code(response) == "AUTH_CODE_EXPIRED"


def test_old_code_is_rejected_after_a_new_one(client: TestClient, app: FastAPI, mailer: FakeMailer) -> None:
    email = unique_email("rotate")
    request_code(client, email)
    old = latest_code(mailer, email)
    age_latest_code(app, email, 61)
    assert request_code(client, email).status_code == 202
    new = latest_code(mailer, email)
    if new == old:  # One-in-a-million collision: the old code would be the new code.
        pytest.skip("random codes collided")
    response = verify(client, email, old)
    assert response.status_code == 422
    assert error_code(response) in {"AUTH_CODE_INVALID", "AUTH_CODE_EXPIRED"}
    assert verify(client, email, new).status_code == 200


# Resend interval --------------------------------------------------------------------------------


def test_resend_within_sixty_seconds_is_rate_limited(client: TestClient, app: FastAPI, mailer: FakeMailer) -> None:
    email = unique_email("rate")
    first = request_code(client, email)
    assert first.status_code == 202
    available_at = first.json()["resend_available_at"]
    assert available_at.endswith("Z")
    second = request_code(client, email)
    assert second.status_code == 429
    assert error_code(second) == "AUTH_RATE_LIMITED"
    assert second.json()["error"]["message"] == "인증 코드를 너무 자주 요청했습니다. 잠시 후 다시 시도해 주세요."
    details = second.json()["error"]["details"]
    assert datetime.fromisoformat(details["resend_available_at"]) == datetime.fromisoformat(available_at)
    assert len([d for d in mailer.deliveries if d.email == email]) == 1

    age_latest_code(app, email, 61)
    third = request_code(client, email)
    assert third.status_code == 202
    assert len([d for d in mailer.deliveries if d.email == email]) == 2
    row = latest_code_row(app, email)
    assert datetime.fromisoformat(third.json()["resend_available_at"]) - row.created_at == timedelta(seconds=60)


def test_response_does_not_reveal_whether_the_account_exists(client: TestClient, app: FastAPI,
                                                             mailer: FakeMailer) -> None:
    existing = unique_email("known")
    login(client, mailer, existing)
    age_latest_code(app, existing, 61)
    known = request_code(client, existing)
    unknown = request_code(client, unique_email("unknown"))
    assert known.status_code == unknown.status_code == 202
    assert set(known.json()) == set(unknown.json()) == {"resend_available_at"}


# Idempotency ------------------------------------------------------------------------------------


def test_email_code_replay_returns_the_same_response_and_sends_once(client: TestClient, mailer: FakeMailer) -> None:
    email = unique_email("replay")
    headers = new_key("code")
    first = request_code(client, email, headers)
    replay = request_code(client, email, headers)
    assert first.status_code == replay.status_code == 202
    assert first.json() == replay.json()
    assert len([d for d in mailer.deliveries if d.email == email]) == 1


def test_email_code_key_reused_with_another_email_conflicts(client: TestClient) -> None:
    headers = new_key("code")
    assert request_code(client, unique_email("one"), headers).status_code == 202
    conflict = request_code(client, unique_email("two"), headers)
    assert conflict.status_code == 409
    assert error_code(conflict) == "IDEMPOTENCY_CONFLICT"


def test_verify_replay_returns_the_same_me_and_sets_a_cookie_again(client: TestClient, mailer: FakeMailer) -> None:
    email = unique_email("verify-replay")
    request_code(client, email)
    code = latest_code(mailer, email)
    headers = new_key("verify")
    first = verify(client, email, code, headers)
    replay = verify(client, email, code, headers)
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    first_token = first.cookies.get("ramus_session")
    replay_token = replay.cookies.get("ramus_session")
    assert first_token and replay_token and first_token != replay_token
    assert client.get(ME_PATH).json() == first.json()


def test_verify_key_reused_with_another_code_conflicts(client: TestClient, mailer: FakeMailer) -> None:
    email = unique_email("verify-conflict")
    request_code(client, email)
    code = latest_code(mailer, email)
    headers = new_key("verify")
    assert verify(client, email, wrong_code(code), headers).status_code == 422
    conflict = verify(client, email, code, headers)
    assert conflict.status_code == 409
    assert error_code(conflict) == "IDEMPOTENCY_CONFLICT"


def test_wrong_code_replay_counts_one_attempt(client: TestClient, app: FastAPI, mailer: FakeMailer) -> None:
    email = unique_email("attempts")
    request_code(client, email)
    bad = wrong_code(latest_code(mailer, email))
    headers = new_key("verify")
    for _ in range(3):
        assert error_code(verify(client, email, bad, headers)) == "AUTH_CODE_INVALID"
    assert latest_code_row(app, email).attempts == 1
