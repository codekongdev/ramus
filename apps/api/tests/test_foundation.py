from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from ramus_api.infrastructure.receipts import ReceiptRow
from ramus_api.main import create_app
from ramus_api.modules.access.infrastructure import MembershipRow, SessionRow
from ramus_api.modules.conversations.infrastructure import ConversationRepository
from ramus_api.shared.domain import token_hash


def login(client, email="minseo@ramus.local"):
    response = client.post("/api/auth/login", json={"email": email, "password": "ramus-demo-2026"})
    assert response.status_code == 200, response.text
    return response.json()


def message_payload(state, **overrides):
    return {
        "project_id": state["project"]["id"],
        "conversation_id": state["conversations"][0]["id"],
        "content": "함께 기록하는 메시지",
        "request_id": str(uuid4()),
        **overrides,
    }


def test_two_authenticated_users_share_author_order_and_persisted_messages(client, app, settings):
    minseo = login(client)
    state = client.get("/api/state").json()
    with TestClient(app) as other:
        jihoon = login(other, "jihoon@ramus.local")
        assert jihoon["id"] != minseo["id"]
        assert other.cookies["ramus_session"] != client.cookies["ramus_session"]
        first = client.post("/api/messages", json=message_payload(state)).json()["message"]
        second = other.post("/api/messages", json=message_payload(state, content="지훈의 의견")).json()["message"]
        assert first["author_id"] == minseo["id"] and second["author_id"] == jihoon["id"]
        assert first["sequence"] < second["sequence"]
        assert client.get("/api/state").json()["messages"] == other.get("/api/state").json()["messages"]
    with TestClient(create_app(settings)) as restarted:
        login(restarted)
        assert restarted.get("/api/state").json()["messages"] == [first, second]


def test_cookie_session_is_hashed_httponly_and_revocable(client, app):
    assert client.get("/api/state").status_code == 401
    assert client.post("/api/auth/login", json={"email": "minseo@ramus.local", "password": "wrong"}).status_code == 401
    response = client.post("/api/auth/login", json={"email": "minseo@ramus.local", "password": "ramus-demo-2026"})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    token = client.cookies["ramus_session"]
    with app.state.database.transaction() as session:
        row = session.scalar(select(SessionRow))
        assert row.token_hash == token_hash(token) and row.token_hash != token
    assert client.get("/api/auth/me").json()["name"] == "민서"
    assert client.post("/api/auth/logout").json() == {"ok": True}
    client.cookies.set("ramus_session", token)
    assert client.get("/api/auth/me").status_code == 401


def test_expired_session_cannot_read_or_replay_a_message(client, app):
    login(client)
    payload = message_payload(client.get("/api/state").json())
    assert client.post("/api/messages", json=payload).status_code == 200
    with app.state.database.transaction() as session:
        session.scalar(select(SessionRow)).expires_at = "2000-01-01T00:00:00+00:00"
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/messages", json=payload).status_code == 401


def test_idempotency_preserves_exact_response_and_rejects_changed_input(client):
    login(client)
    state = client.get("/api/state").json()
    payload = message_payload(state)
    first = client.post("/api/messages", json=payload)
    assert first.status_code == 200
    assert client.post("/api/messages", json=payload).json() == first.json()
    assert len(client.get("/api/state").json()["messages"]) == 1
    conflict = client.post("/api/messages", json={**payload, "content": "같은 ID의 다른 입력"})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_membership_revocation_blocks_reads_writes_and_cached_replays(client, app):
    user = login(client)
    state = client.get("/api/state").json()
    payload = message_payload(state)
    assert client.post("/api/messages", json=payload).status_code == 200
    with app.state.database.transaction() as session:
        membership = session.scalar(select(MembershipRow).where(MembershipRow.user_id == user["id"]))
        session.delete(membership)
    assert client.get("/api/state", params={"project_id": state["project"]["id"]}).status_code == 404
    assert client.get("/api/projects").json() == []
    assert client.post("/api/messages", json=payload).status_code == 404
    assert client.post("/api/messages", json={**payload, "request_id": str(uuid4())}).status_code == 404


def test_project_copy_is_idempotent_and_prevents_cross_project_conversation_ids(client):
    login(client)
    before = client.get("/api/state").json()
    payload = {"name": "격리된 논의", "request_id": str(uuid4())}
    created = client.post("/api/projects", json=payload)
    assert created.status_code == 200
    project = created.json()
    assert client.post("/api/projects", json=payload).json() == project
    assert len(client.get("/api/projects").json()) == 2
    assert client.get("/api/state", params={"project_id": before["project"]["id"]}).json() == before
    copied = client.get("/api/state", params={"project_id": project["id"]}).json()
    assert copied["messages"] == [] and len(copied["members"]) == 2
    invalid = message_payload(before, project_id=project["id"])
    assert client.post("/api/messages", json=invalid).status_code == 404
    assert client.post("/api/projects", json={**payload, "name": "다른 사본"}).status_code == 409


def test_failed_message_transaction_rolls_back_message_sequence_and_receipt(client, app, monkeypatch):
    login(client)
    state = client.get("/api/state").json()
    payload = message_payload(state)
    original = ConversationRepository.add_message

    def fail_after_insert(repository, data):
        original(repository, data)
        raise RuntimeError("controlled storage failure")

    monkeypatch.setattr(ConversationRepository, "add_message", fail_after_insert)
    with pytest.raises(RuntimeError, match="controlled storage"):
        client.post("/api/messages", json=payload)
    assert client.get("/api/state").json()["messages"] == []
    with app.state.database.transaction() as session:
        assert session.scalar(select(ReceiptRow)) is None
    monkeypatch.setattr(ConversationRepository, "add_message", original)
    retry = client.post("/api/messages", json=payload)
    assert retry.status_code == 200 and retry.json()["message"]["sequence"] == 1


def test_origin_validation_and_schema_errors_do_not_echo_submitted_credentials(client):
    request = {"email": "minseo@ramus.local", "password": "submitted-secret"}
    blocked = client.post("/api/auth/login", headers={"origin": "https://untrusted.example"}, json=request)
    assert blocked.status_code == 403
    blocked = client.post("/api/auth/login", headers={"sec-fetch-site": "cross-site"}, json=request)
    assert blocked.status_code == 403
    invalid = client.post("/api/auth/login", json={**request, "unexpected": "submitted-secret"})
    assert invalid.status_code == 422 and "submitted-secret" not in invalid.text
    login(client)
    state = client.get("/api/state").json()
    forged = client.post("/api/messages", json={**message_payload(state), "author_id": "other"})
    assert forged.status_code == 422
    assert client.post("/api/messages", json=message_payload(state, content="  \n  ")).status_code == 422


def test_same_origin_and_cors_preflight_are_supported(client):
    origin = "http://127.0.0.1:5173"
    response = client.options("/api/messages", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    response = client.post(
        "/api/auth/login", headers={"Origin": origin},
        json={"email": "minseo@ramus.local", "password": "ramus-demo-2026"},
    )
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"


def test_demo_seed_does_not_reset_existing_discussion(client, app):
    login(client)
    payload = message_payload(client.get("/api/state").json())
    saved = client.post("/api/messages", json=payload).json()["message"]
    app.state.workspace.ensure_demo()
    assert len(client.get("/api/projects").json()) == 1
    assert client.get("/api/state").json()["messages"] == [saved]


def test_startup_does_not_create_schema_or_seed(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok", "service": "ramus"}
        assert inspect(app.state.database.engine).get_table_names() == []


def test_ai_mention_remains_plain_text_without_jobs_or_future_features(client, app):
    login(client)
    state = client.get("/api/state").json()
    response = client.post("/api/messages", json=message_payload(state, content="@AI 아직은 일반 텍스트"))
    assert response.status_code == 200
    assert set(response.json()) == {"message"}
    assert response.json()["message"]["role"] == "user"
    assert set(state) == {"user", "project", "members", "conversations", "messages"}
    assert set(inspect(app.state.database.engine).get_table_names()) == {
        "users", "sessions", "projects", "memberships", "conversations", "messages", "request_receipts",
    }


def test_project_creation_replay_cannot_reveal_a_project_after_membership_revocation(client, app):
    user = login(client)
    payload = {"name": "접근 취소 시험", "request_id": str(uuid4())}
    created = client.post("/api/projects", json=payload)
    assert created.status_code == 200
    with app.state.database.transaction() as session:
        membership = session.scalar(select(MembershipRow).where(
            MembershipRow.user_id == user["id"], MembershipRow.project_id == created.json()["id"],
        ))
        session.delete(membership)
    assert client.post("/api/projects", json=payload).status_code == 404


@pytest.mark.parametrize("field", ["content", "request_id", "project_id", "conversation_id"])
@pytest.mark.parametrize("invalid", ["\x00", "\ud800"])
def test_invalid_database_text_is_rejected_without_echoing_input(client, field, invalid):
    import json

    login(client)
    payload = message_payload(client.get("/api/state").json(), **{field: "submitted-secret" + invalid})
    response = client.post("/api/messages", content=json.dumps(payload), headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "submitted-secret" not in response.text
    assert client.get("/api/state").json()["messages"] == []


@pytest.mark.parametrize("invalid", ["\x00", "\ud800"])
def test_invalid_project_and_login_text_is_rejected_before_database_access(client, invalid):
    import json

    for field in ("email", "password"):
        payload = {"email": "minseo@ramus.local", "password": "ramus-demo-2026", field: "submitted-secret" + invalid}
        response = client.post("/api/auth/login", content=json.dumps(payload), headers={"Content-Type": "application/json"})
        assert response.status_code == 422 and "submitted-secret" not in response.text
    login(client)
    for field in ("name", "request_id"):
        payload = {"name": "test", "request_id": str(uuid4()), field: "submitted-secret" + invalid}
        response = client.post("/api/projects", content=json.dumps(payload), headers={"Content-Type": "application/json"})
        assert response.status_code == 422 and "submitted-secret" not in response.text


def test_state_project_id_rejects_null_byte_and_oversized_identifier(client):
    login(client)
    assert client.get("/api/state", params={"project_id": "bad\x00id"}).status_code == 422
    assert client.get("/api/state", params={"project_id": "x" * 37}).status_code == 422


def test_validation_error_with_an_invalid_unicode_field_name_can_be_encoded(client):
    import json

    response = client.post(
        "/api/auth/login", content=json.dumps({"email": "valid@local.test", "password": "secret", "\ud800": "secret"}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422 and "secret" not in response.text
