"""One-time password setup for existing sessions, using only disposable PostgreSQL state."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from login_flow import TEST_PASSWORD, error_code, legacy_login, new_key, unique_email
from sqlalchemy import select, update

from ramus_api.main import create_app
from ramus_api.modules.access.domain.codes import hash_code, hash_session_token
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.access.infrastructure.models import (
    AccountRow,
    AIConnectionRow,
    AuthAttemptRow,
    MembershipRow,
    SessionRow,
)
from ramus_api.modules.access.infrastructure.passwords import ScryptPasswordHasher
from ramus_api.shared.domain import new_id, utc_now
from ramus_api.shared.infrastructure.receipts import RequestReceiptRow

pytestmark = pytest.mark.integration
PATH = "/api/me/password"


@pytest.fixture
def rig(integration_settings):
    mailer = FakeMailer()
    app = create_app(integration_settings, mailer=mailer)
    client = TestClient(app, client=(f"setup-{uuid4().hex}", 50000))
    identity = legacy_login(client, mailer, unique_email("legacy-setup")).json()
    account_id = UUID(identity["account"]["id"])
    token = client.cookies.get("ramus_session")
    with app.state.container.database.transaction() as transaction:
        session_id = transaction.scalar(select(SessionRow.id).where(SessionRow.token_hash == hash_session_token(token)))
    try:
        yield app, client, identity, account_id, session_id, token
    finally:
        client.close()
        app.state.container.database.dispose()


def setup(client, password=TEST_PASSWORD, key=None, **extra):
    return client.put(PATH, json={"password": password, **extra}, headers=key or new_key())


def test_legacy_session_can_set_password_without_changing_its_account_or_work(rig, caplog):
    app, client, identity, account_id, session_id, token = rig
    with app.state.container.database.transaction() as transaction:
        transaction.add(AIConnectionRow(account_id=account_id, provider="openai", ciphertext="fixture-ciphertext",
                                        status="connected", verified_at=utc_now()))
        memberships = transaction.scalars(select(MembershipRow.project_id).where(MembershipRow.account_id == account_id)).all()
    project_id = identity["default_project_id"]
    created = client.post(f"/api/projects/{project_id}/conversations", json={"title": "기존 작업 유지"}, headers=new_key())
    assert created.status_code == 200, created.text
    assert client.get(PATH).json() == {"configured": False}
    key = new_key("setup")
    response = setup(client, key=key)
    assert response.status_code == 200 and response.json() == {"configured": True}
    assert "set-cookie" not in response.headers
    assert client.cookies.get("ramus_session") == token
    assert client.get(PATH).json() == {"configured": True}
    assert client.get("/api/me").json()["account"] == identity["account"]
    assert client.get(f"/api/conversations/{created.json()['id']}").status_code == 200
    with app.state.container.database.transaction() as transaction:
        account = transaction.get(AccountRow, account_id)
        assert ScryptPasswordHasher().verify(TEST_PASSWORD, account.password_hash)
        assert transaction.get(SessionRow, session_id).revoked_at is None
        assert transaction.get(AIConnectionRow, account_id).ciphertext == "fixture-ciphertext"
        assert transaction.scalars(select(MembershipRow.project_id).where(MembershipRow.account_id == account_id)).all() == memberships
        receipt = transaction.scalar(select(RequestReceiptRow).where(RequestReceiptRow.idempotency_key == key["Idempotency-Key"]))
        assert receipt.actor_id == str(account_id) and str(session_id) in receipt.scope
        assert receipt.response == {"configured": True}
        assert TEST_PASSWORD not in str(receipt.response) + receipt.fingerprint + receipt.scope
    assert TEST_PASSWORD not in response.text + caplog.text
    assert client.post("/api/auth/logout", json={}, headers=new_key()).status_code == 200
    signed_in = client.post("/api/auth/login", json={"email": identity["account"]["email"], "password": TEST_PASSWORD}, headers=new_key())
    assert signed_in.status_code == 200 and signed_in.json()["account"] == identity["account"]


def test_set_password_is_idempotent_only_for_same_session_and_payload(rig):
    app, client, _, account_id, _, _ = rig
    key = new_key("replay-setup")
    assert setup(client, key=key).status_code == 200
    assert setup(client, key=key).status_code == 200
    conflict = setup(client, "another-test-password", key=key)
    assert conflict.status_code == 409 and error_code(conflict) == "IDEMPOTENCY_CONFLICT"
    already = setup(client)
    assert already.status_code == 409 and error_code(already) == "PASSWORD_ALREADY_SET"
    other_token = f"synthetic-session-{uuid4().hex}"
    with app.state.container.database.transaction() as transaction:
        transaction.add(SessionRow(id=new_id(), account_id=account_id, token_hash=hash_session_token(other_token),
                                   expires_at=utc_now() + timedelta(days=1)))
    other = TestClient(app, client=(f"other-session-{uuid4().hex}", 50000))
    other.cookies.set("ramus_session", other_token)
    try:
        assert other.get(PATH).json() == {"configured": True}
        response = setup(other, key=key)
        assert response.status_code == 409 and error_code(response) == "PASSWORD_ALREADY_SET"
    finally:
        other.close()


@pytest.mark.parametrize("change", [{"revoked_at": utc_now()}, {"expires_at": utc_now() - timedelta(seconds=1)}])
def test_expired_or_revoked_session_cannot_read_setup_or_replay_it(rig, change):
    app, client, _, account_id, session_id, _ = rig
    key = new_key()
    assert setup(client, key=key).status_code == 200
    with app.state.container.database.transaction() as transaction:
        transaction.execute(update(SessionRow).where(SessionRow.id == session_id).values(**change))
        before = transaction.get(AccountRow, account_id).password_hash
    assert client.get(PATH).status_code == 401
    assert setup(client, key=key).status_code == 401
    with app.state.container.database.transaction() as transaction:
        assert transaction.get(AccountRow, account_id).password_hash == before


def test_anonymous_and_payload_account_selection_are_rejected(rig):
    app, client, _, account_id, _, _ = rig
    anonymous = TestClient(app)
    try:
        assert anonymous.get(PATH).status_code == 401
        assert setup(anonymous).status_code == 401
    finally:
        anonymous.close()
    for extra in ({"account_id": str(new_id())}, {"email": unique_email("someone-else")}):
        assert setup(client, **extra).status_code == 422
    with app.state.container.database.transaction() as transaction:
        assert transaction.get(AccountRow, account_id).password_hash is None


def test_another_account_session_sets_only_its_own_password(rig):
    app, owner, _, account_id, _, _ = rig
    other_id, other_token = new_id(), f"other-account-{uuid4().hex}"
    with app.state.container.database.transaction() as transaction:
        transaction.add(AccountRow(id=other_id, email=unique_email("other-account"), display_name="다른 계정"))
        transaction.flush()
        transaction.add(SessionRow(id=new_id(), account_id=other_id, token_hash=hash_session_token(other_token),
                                   expires_at=utc_now() + timedelta(days=1)))
    other = TestClient(app)
    other.cookies.set("ramus_session", other_token)
    try:
        assert setup(other).status_code == 200
        assert owner.get(PATH).json() == {"configured": False}
        with app.state.container.database.transaction() as transaction:
            assert transaction.get(AccountRow, account_id).password_hash is None
            assert transaction.get(AccountRow, other_id).password_hash is not None
    finally:
        other.close()


def test_parallel_initial_password_updates_have_one_winner(rig):
    app, _, _, account_id, _, token = rig

    def attempt(index):
        client = TestClient(app, client=(f"setup-race-{uuid4().hex}", 50000))
        client.cookies.set("ramus_session", token)
        try:
            return setup(client, f"parallel-setup-password-{index}")
        finally:
            client.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(index for index, response in enumerate(responses) if response.status_code == 200)
    with app.state.container.database.transaction() as transaction:
        encoded = transaction.get(AccountRow, account_id).password_hash
    assert ScryptPasswordHasher().verify(f"parallel-setup-password-{winner}", encoded)
    assert not ScryptPasswordHasher().verify(f"parallel-setup-password-{1 - winner}", encoded)


@pytest.mark.parametrize("replay", [False, True])
def test_revocation_after_route_authentication_cannot_mutate_or_replay(rig, monkeypatch, replay):
    app, client, _, account_id, session_id, _ = rig
    key = new_key("revocation-race")
    if replay:
        assert setup(client, key=key).status_code == 200
    original = ScryptPasswordHasher.hash

    def revoke_during_hash(self, password):
        with app.state.container.database.transaction() as transaction:
            transaction.execute(update(SessionRow).where(SessionRow.id == session_id).values(revoked_at=utc_now()))
        return original(self, password)

    monkeypatch.setattr(ScryptPasswordHasher, "hash", revoke_during_hash)
    response = setup(client, key=key)
    assert response.status_code == 401 and error_code(response) == "UNAUTHORIZED"
    with app.state.container.database.transaction() as transaction:
        assert (transaction.get(AccountRow, account_id).password_hash is not None) == replay
        count = len(transaction.scalars(select(RequestReceiptRow).where(RequestReceiptRow.idempotency_key == key["Idempotency-Key"])).all())
        assert count == int(replay)


@pytest.mark.parametrize("subject,limit", [("email", 10), ("ip", 60)])
def test_initial_password_setup_enforces_existing_rate_limits(rig, subject, limit):
    app, client, identity, account_id, _, _ = rig
    value = identity["account"]["email"] if subject == "email" else client._transport.client[0]
    digest = hash_code(f"{subject}:{value}", "password_setup", app.state.container.settings.auth_secret.get_secret_value())
    with app.state.container.database.transaction() as transaction:
        transaction.add_all([AuthAttemptRow(id=new_id(), scope="password_setup", subject_hash=digest, created_at=utc_now())
                             for _ in range(limit)])
    assert setup(client).status_code == 429
    with app.state.container.database.transaction() as transaction:
        assert transaction.get(AccountRow, account_id).password_hash is None
