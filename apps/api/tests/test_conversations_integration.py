"""A2 HTTP collaboration against a migrated, disposable PostgreSQL database."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from login_flow import login, new_key, unique_email
from sqlalchemy import delete, func, select

from ramus_api.main import create_app
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.access.infrastructure.models import AIConnectionRow, MembershipRow
from ramus_api.modules.conversations.infrastructure.models import ConversationRow, MessageRow
from ramus_api.modules.execution.infrastructure.models import RunRow
from ramus_api.modules.projects.infrastructure.models import ProjectRow
from ramus_api.shared.domain.primitives import utc_now
from ramus_api.shared.infrastructure.receipts import RequestReceiptRow

pytestmark = pytest.mark.integration


@pytest.fixture
def workspace(integration_settings):
    mailer = FakeMailer()
    app = create_app(integration_settings, mailer=mailer)
    client_host = f"a2-{uuid4().hex}"
    with ExitStack() as stack:
        first = stack.enter_context(TestClient(app, client=(client_host, 50000)))
        # One lifespan owns the event loop; other clients only send ordinary HTTP requests.
        second = TestClient(app, client=(client_host, 50001))
        stack.callback(second.close)
        one = login(first, mailer, unique_email("alice")).json()
        two = login(second, mailer, unique_email("bob")).json()
        assert one["default_project_id"] == two["default_project_id"]
        yield app, first, second, one, two


def create_conversation(client, project_id, title="새 대화", headers=None):
    response = client.post(
        f"/api/projects/{project_id}/conversations", json={"title": title}, headers=headers or new_key()
    )
    assert response.status_code == 200, response.text
    return response.json()


def post_message(client, conversation_id, body="논의", headers=None):
    return client.post(
        f"/api/conversations/{conversation_id}/messages", json={"body": body}, headers=headers or new_key()
    )


def test_tree_search_ancestors_and_literal_search(workspace):
    app, first, second, one, _ = workspace
    project = one["default_project_id"]
    root = create_conversation(first, project, "Root " + uuid4().hex)
    child_id, grandchild_id = uuid4(), uuid4()
    with app.state.container.database.transaction() as session:
        session.add(ConversationRow(
            id=child_id, project_id=UUID(project), parent_id=UUID(root["id"]),
            title="동명_대화%", origin="branch", created_by=UUID(one["account"]["id"]),
        ))
        session.flush()
        session.add(ConversationRow(
            id=grandchild_id, project_id=UUID(project), parent_id=child_id,
            title="동명_대화%", origin="branch", created_by=UUID(one["account"]["id"]),
        ))
    response = second.get(f"/api/projects/{project}/conversations")
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}
    assert items[root["id"]]["path"] == []
    assert items[str(child_id)]["path"] == [root["title"]]
    assert items[str(grandchild_id)]["path"] == [root["title"], "동명_대화%"]
    search = second.get(f"/api/projects/{project}/conversations/search", params={
        "q": "_대화%", "exclude_id": str(child_id),
    })
    assert search.status_code == 200
    assert [item["id"] for item in search.json()["items"]] == [str(grandchild_id)]
    detail = second.get(f"/api/conversations/{grandchild_id}")
    assert detail.status_code == 200
    assert detail.json() == {**items[str(grandchild_id)], "active_run": None}


def test_two_accounts_author_order_and_reconnect_cursor(workspace):
    _, first, second, one, two = workspace
    root = create_conversation(first, one["default_project_id"])
    conversation = root["id"]
    sent = []
    for client, body, account in [(first, "첫 메시지", one), (second, "다음 메시지", two)]:
        response = post_message(client, conversation, body)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["run"] is None
        message = data["message"]
        assert message["author"] == {
            "kind": "human", "account_id": account["account"]["id"],
            "display_name": account["account"]["display_name"],
        }
        assert message["conversation_id"] == conversation
        assert message["body"] == body
        assert message["is_example"] is False
        assert message["run_id"] is None
        sent.append(message)
    assert sent[0]["seq"] < sent[1]["seq"]
    page = second.get(f"/api/conversations/{conversation}/messages", params={"limit": 1}).json()
    assert page == {"items": sent[:1], "next_after_seq": sent[0]["seq"]}
    recovered = first.get(f"/api/conversations/{conversation}/messages", params={
        "after_seq": page["next_after_seq"], "limit": 1,
    }).json()
    assert recovered == {"items": sent[1:], "next_after_seq": None}
    assert first.get(f"/api/conversations/{conversation}/messages", params={
        "after_seq": sent[-1]["seq"],
    }).json() == {"items": [], "next_after_seq": None}


def test_concurrent_messages_have_unique_committed_order(workspace):
    _, first, second, one, _ = workspace
    conversation = create_conversation(first, one["default_project_id"])["id"]
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(post_message, first if i % 2 else second, conversation, f"m-{i}")
                   for i in range(16)]
        responses = [future.result(timeout=15) for future in futures]
    assert [response.status_code for response in responses] == [200] * 16
    messages = first.get(f"/api/conversations/{conversation}/messages").json()["items"]
    assert {message["body"] for message in messages} == {f"m-{i}" for i in range(16)}
    seqs = [message["seq"] for message in messages]
    assert len(set(seqs)) == 16
    assert seqs == sorted(seqs)


def test_idempotency_concurrent_replay_conflict_and_actor_scoping(workspace):
    app, first, second, one, _ = workspace
    project = one["default_project_id"]
    key = new_key()
    root = create_conversation(first, project, headers=key)
    assert create_conversation(first, project, headers=key) == root
    conflict = first.post(f"/api/projects/{project}/conversations", json={"title": "다른 제목"}, headers=key)
    assert conflict.status_code == 409
    key = new_key()
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(post_message, first, root["id"], "한 번만", key) for _ in range(5)]
        responses = [future.result(timeout=15) for future in futures]
    assert [response.status_code for response in responses] == [200] * 5
    assert all(response.json() == responses[0].json() for response in responses)
    assert post_message(first, root["id"], "다른 본문", key).status_code == 409
    independent = post_message(second, root["id"], "한 번만", key)
    assert independent.status_code == 200
    assert independent.json()["message"]["id"] != responses[0].json()["message"]["id"]
    with app.state.container.database.transaction() as session:
        count = session.scalar(select(func.count()).select_from(MessageRow).where(
            MessageRow.conversation_id == UUID(root["id"])))
    assert count == 2


def test_project_membership_hides_resources_and_is_rechecked_for_replay(workspace):
    app, first, second, one, _ = workspace
    private_id = uuid4()
    account_id = UUID(one["account"]["id"])
    with app.state.container.database.transaction() as session:
        session.add(ProjectRow(id=private_id, name="Private", is_shared_sample=False))
        session.flush()
        session.add(MembershipRow(project_id=private_id, account_id=account_id, role="editor"))
    key = new_key()
    root = create_conversation(first, private_id, headers=key)
    message_key = new_key()
    assert post_message(first, root["id"], headers=message_key).status_code == 200
    paths = [
        f"/api/projects/{private_id}/conversations",
        f"/api/projects/{private_id}/conversations/search",
        f"/api/conversations/{root['id']}",
        f"/api/conversations/{root['id']}/messages",
        f"/api/projects/{private_id}/events",
    ]
    for path in paths:
        response = second.get(path)
        assert response.status_code == 404, (path, response.text)
        assert response.json()["error"]["code"] == "NOT_FOUND"
    assert post_message(second, root["id"]).status_code == 404
    assert second.post(f"/api/projects/{private_id}/conversations", json={"title": "blocked"},
                       headers=new_key()).status_code == 404
    with app.state.container.database.transaction() as session:
        session.execute(delete(MembershipRow).where(MembershipRow.project_id == private_id))
    assert first.post(f"/api/projects/{private_id}/conversations", json={"title": "새 대화"},
                      headers=key).status_code == 404
    assert post_message(first, root["id"], headers=message_key).status_code == 404
    assert first.get(f"/api/conversations/{uuid4()}").status_code == 404


def test_ai_registration_is_atomic_and_uses_requesters_connection(workspace):
    app, first, second, one, _ = workspace
    conversation = create_conversation(first, one["default_project_id"])["id"]
    rejected_key = new_key()
    rejected = post_message(first, conversation, "@Ai 설명해줘", rejected_key)
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "AI_CONNECTION_REQUIRED"
    with app.state.container.database.transaction() as session:
        assert session.scalar(select(RequestReceiptRow.id).where(
            RequestReceiptRow.idempotency_key == rejected_key["Idempotency-Key"])) is None
        session.add(AIConnectionRow(account_id=UUID(one["account"]["id"]), provider="openai",
                                    ciphertext="test-encrypted-value", status="connected", verified_at=utc_now()))
    accepted = post_message(first, conversation, "@Ai 설명해줘", rejected_key)
    assert accepted.status_code == 200, accepted.text
    run = accepted.json()["run"]
    assert run["purpose"] == "work"
    assert run["status"] == "pending"
    assert run["requested_by"] == one["account"]["id"]
    assert post_message(first, conversation, "@Ai 설명해줘", rejected_key).json() == accepted.json()
    assert first.get(f"/api/conversations/{conversation}").json()["active_run"] == run
    active = post_message(first, conversation, "@AI 다시")
    assert active.status_code == 409
    assert active.json()["error"]["code"] == "ACTIVE_RUN_EXISTS"
    # Another member cannot borrow the first member's connection.
    assert post_message(second, conversation, "@AI 다른 요청").json()["error"]["code"] == "AI_CONNECTION_REQUIRED"
    assert post_message(second, conversation, "사람 논의는 계속").status_code == 200
    with app.state.container.database.transaction() as session:
        stored = session.get(RunRow, UUID(run["id"]))
        assert stored.credential_account_id == UUID(one["account"]["id"])
        assert session.scalar(select(func.count()).select_from(MessageRow).where(
            MessageRow.conversation_id == UUID(conversation))) == 2


@pytest.mark.parametrize("payload", [
    {"body": ""}, {"body": " \n\t"}, {"body": "a" * 20_001}, {"body": "private\x00text"},
    {"body": "hello", "seq": 999}, {"body": "hello", "author_account_id": str(uuid4())},
    {"body": "hello", "author": {"kind": "ai"}},
])
def test_message_boundary_rejects_invalid_or_spoofed_fields(workspace, payload):
    _, first, _, one, _ = workspace
    conversation = create_conversation(first, one["default_project_id"])["id"]
    response = first.post(f"/api/conversations/{conversation}/messages", json=payload, headers=new_key())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"
    assert first.get(f"/api/conversations/{conversation}/messages").json()["items"] == []


def test_title_and_cursor_validation(workspace):
    _, first, _, one, _ = workspace
    project = one["default_project_id"]
    for title in ("", "\n \t", "a" * 101, "private\x00text"):
        assert first.post(f"/api/projects/{project}/conversations", json={"title": title},
                          headers=new_key()).status_code == 422
    conversation = create_conversation(first, project)["id"]
    for params in ({"after_seq": -1}, {"limit": 0}, {"limit": 201}):
        assert first.get(f"/api/conversations/{conversation}/messages", params=params).status_code == 422
    assert first.get(f"/api/conversations/{conversation}/messages", params={"limit": 200}).status_code == 200


def test_postgres_incompatible_text_never_reaches_storage_or_logs(workspace, caplog):
    _, first, _, one, _ = workspace
    conversation = create_conversation(first, one["default_project_id"])["id"]
    for escaped in (r"private\u0000text", r"private\ud800text"):
        response = first.post(
            f"/api/conversations/{conversation}/messages",
            content='{"body":"' + escaped + '"}',
            headers={**new_key(), "Content-Type": "application/json"},
        )
        assert response.status_code == 422
        assert "private" not in response.text
        assert "private" not in caplog.text
    assert first.get(f"/api/conversations/{conversation}/messages").json()["items"] == []


def test_logged_out_requests_are_rejected(integration_settings):
    with TestClient(create_app(integration_settings)) as client:
        assert client.get(f"/api/projects/{uuid4()}/conversations").status_code == 401
        assert client.get(f"/api/conversations/{uuid4()}/messages").status_code == 401
        assert client.get(f"/api/projects/{uuid4()}/events").status_code == 401
        assert post_message(client, uuid4()).status_code == 401


def test_http_changes_publish_once_after_commit_and_failures_publish_nothing(workspace):
    app, first, second, one, _ = workspace
    container = app.state.container
    project = UUID(one["default_project_id"])
    subscription = first.portal.call(container.events.subscribe, project)
    try:
        create_key = new_key()
        conversation = create_conversation(first, project, headers=create_key)
        first.portal.call(container.event_relay.flush)
        created = first.portal.call(subscription.next, 0.2)
        assert created.name == "conversation.created"
        assert created.data["conversation"]["id"] == UUID(conversation["id"])
        # The receiving account can read the resource as soon as its event arrives.
        assert second.get(f"/api/conversations/{conversation['id']}").status_code == 200
        assert create_conversation(first, project, headers=create_key) == conversation
        first.portal.call(container.event_relay.flush)
        assert first.portal.call(subscription.next, 0.01) is None

        key = new_key()
        sent = post_message(first, conversation["id"], "본문은 SSE에 싣지 않음", key)
        assert sent.status_code == 200
        first.portal.call(container.event_relay.flush)
        event = first.portal.call(subscription.next, 0.2)
        assert event.name == "message.created"
        assert set(event.data) == {"conversation_id", "message_id", "seq"}
        assert str(event.data["message_id"]) == sent.json()["message"]["id"]
        messages = second.get(f"/api/conversations/{conversation['id']}/messages").json()["items"]
        assert messages == [sent.json()["message"]]
        assert post_message(first, conversation["id"], "본문은 SSE에 싣지 않음", key).json() == sent.json()
        assert post_message(first, conversation["id"], "@AI 연결 없이 요청").status_code == 409
        first.portal.call(container.event_relay.flush)
        assert first.portal.call(subscription.next, 0.01) is None
    finally:
        first.portal.call(subscription.close)
