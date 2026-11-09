"""A8 project creation is atomic, idempotent, and visible only to its participants."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from login_flow import login, new_key, unique_email
from sqlalchemy import text

from ramus_api.main import create_app
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.access.public import MembershipWriter

pytestmark = pytest.mark.integration


@pytest.fixture
def workspace(integration_settings):
    mailer = FakeMailer()
    app = create_app(integration_settings, mailer=mailer)
    with ExitStack() as stack:
        clients = [stack.enter_context(TestClient(app)) for _ in range(2)]
        profiles = [login(client, mailer, unique_email("project-owner")).json() for client in clients]
        yield app, clients, profiles


def create(client, name, headers=None):
    return client.post("/api/projects", json={"name": name}, headers=headers or new_key("project"))


def test_project_creation_and_search_require_login(integration_settings):
    with TestClient(create_app(integration_settings)) as client:
        response = create(client, "Unauthenticated")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"
        assert client.get("/api/projects/search").status_code == 401


def test_created_project_has_only_its_creator_and_can_be_used_immediately(workspace):
    app, (creator, outsider), profiles = workspace
    sample_id = profiles[0]["default_project_id"]
    sample = creator.get("/api/projects").json()["items"][0]
    response = create(creator, "새 작업 공간")
    assert response.status_code == 200
    project = response.json()
    assert project == {"id": project["id"], "name": "새 작업 공간", "is_shared_sample": False}
    assert project["id"] != sample_id
    assert creator.get("/api/projects").json()["items"] == [sample, project]
    assert outsider.get("/api/projects").json()["items"] == [sample]
    assert creator.get(f"/api/projects/{project['id']}/participants").json() == {
        "items": [profiles[0]["account"]]
    }
    assert creator.get(f"/api/projects/{project['id']}/conversations").json() == {"items": []}
    conversation = creator.post(
        f"/api/projects/{project['id']}/conversations", json={"title": "첫 대화"},
        headers=new_key("conversation"),
    )
    assert conversation.status_code == 200
    assert conversation.json()["project_id"] == project["id"]
    for path in ("participants", "conversations"):
        assert outsider.get(f"/api/projects/{project['id']}/{path}").status_code == 404
    assert outsider.post(
        f"/api/projects/{project['id']}/conversations", json={"title": "Forbidden"},
        headers=new_key("outsider"),
    ).status_code == 404
    assert creator.get("/api/projects").json()["items"][0] == sample
    assert creator.get("/api/me").json()["default_project_id"] == sample_id
    with app.state.container.database.transaction() as transaction:
        row = transaction.execute(
            text("SELECT account_id, role FROM membership WHERE project_id = :id"),
            {"id": project["id"]},
        ).one()
        assert str(row.account_id) == profiles[0]["account"]["id"]
        assert row.role == "editor"
        assert transaction.scalar(
            text("SELECT seed_key FROM project WHERE id = :id"), {"id": project["id"]}
        ) is None


def test_replay_concurrency_conflict_and_actor_scoping(workspace):
    app, (first, second), profiles = workspace
    key = new_key("same-action")
    name = f"Replay {uuid4()}"
    with ThreadPoolExecutor(max_workers=5) as pool:
        responses = list(pool.map(lambda _: create(first, name, key), range(5)))
    assert all(response.status_code == 200 for response in responses)
    project = responses[0].json()
    assert all(response.json() == project for response in responses)
    conflict = create(first, "Different body", key)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    another = create(second, name, key)
    assert another.status_code == 200
    assert another.json()["id"] != project["id"]
    with app.state.container.database.transaction() as transaction:
        assert transaction.scalar(text("SELECT count(*) FROM project WHERE name = :name"), {"name": name}) == 2
        assert transaction.scalar(
            text("SELECT count(*) FROM membership WHERE account_id = :account_id AND project_id = :project_id"),
            {"account_id": profiles[0]["account"]["id"], "project_id": project["id"]},
        ) == 1


def test_project_search_is_case_insensitive_literal_and_membership_scoped(workspace):
    _, (creator, outsider), _ = workspace
    project = create(creator, "Ramus 100%_Team").json()
    create(creator, "Ramus 100xxTeam")
    hidden = create(outsider, "Ramus 100%_Team").json()
    for query in ("ramus 100%_", "RAMUS 100%_"):
        response = creator.get("/api/projects/search", params={"q": query})
        assert response.status_code == 200
        assert response.json() == {"items": [project]}
    assert outsider.get("/api/projects/search", params={"q": "100%_"}).json() == {"items": [hidden]}
    assert creator.get("/api/projects/search", params={"q": "does not exist"}).json() == {"items": []}
    assert creator.get("/api/projects/search").json() == creator.get("/api/projects").json()


@pytest.mark.parametrize("name", ["", " \t\n", "a" * 101, "bad\x00name"])
def test_invalid_project_names_are_rejected_without_creating_rows(workspace, name):
    _, (creator, _), _ = workspace
    before = creator.get("/api/projects").json()
    response = create(creator, name)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"
    assert creator.get("/api/projects").json() == before


def test_membership_failure_rolls_back_project_and_receipt(workspace, monkeypatch):
    app, (creator, _), profiles = workspace
    key = new_key("rollback")
    name = f"Rollback {uuid4()}"
    original = MembershipWriter.add_creator

    def fail_after_membership(self, transaction, account_id, project_id):
        original(self, transaction, account_id, project_id)
        raise RuntimeError("Synthetic membership failure")

    with monkeypatch.context() as patch:
        patch.setattr(MembershipWriter, "add_creator", fail_after_membership)
        with pytest.raises(RuntimeError, match="Synthetic membership failure"):
            create(creator, name, key)
    with app.state.container.database.transaction() as transaction:
        assert transaction.scalar(text("SELECT count(*) FROM project WHERE name = :name"), {"name": name}) == 0
        assert transaction.scalar(
            text("SELECT count(*) FROM request_receipt WHERE actor_id = :actor AND idempotency_key = :key"),
            {"actor": profiles[0]["account"]["id"], "key": key["Idempotency-Key"]},
        ) == 0
    assert create(creator, name, key).status_code == 200
