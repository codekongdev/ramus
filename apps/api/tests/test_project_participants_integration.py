"""A1: authenticated project/participant reads preserve one shared membership per account."""

from collections.abc import Iterator
from contextlib import ExitStack
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from login_flow import login, unique_email
from sqlalchemy import text

from ramus_api.main import create_app
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
def client(integration_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(integration_settings)) as instance:
        yield instance


def test_project_reads_require_a_session(client: TestClient) -> None:
    for path in ("/api/projects", f"/api/projects/{uuid4()}/participants"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_three_accounts_see_the_same_project_and_participants(fresh_database_url: str, run_alembic) -> None:
    run_alembic(fresh_database_url, "upgrade", "head")
    mailer = FakeMailer()
    app = create_app(Settings(_env_file=None, database_url=fresh_database_url), mailer=mailer)
    with ExitStack() as stack:
        # Share one server lifespan while keeping three independent sessions.
        clients = [stack.enter_context(TestClient(app))]
        for _ in range(2):
            client = TestClient(app)
            stack.callback(client.close)
            clients.append(client)
        profiles = [login(client, mailer, unique_email("participant")).json() for client in clients]
        project_id = profiles[0]["default_project_id"]
        expected = {profile["account"]["id"]: profile["account"] for profile in profiles}
        for client, profile in zip(clients, profiles, strict=True):
            projects = client.get("/api/projects")
            assert projects.status_code == 200
            assert [item["id"] for item in projects.json()["items"]] == [project_id]
            assert projects.json()["items"][0]["is_shared_sample"] is True
            response = client.get(f"/api/projects/{project_id}/participants")
            assert response.status_code == 200
            assert {person["id"]: person for person in response.json()["items"]} == expected
            assert client.get("/api/me").json() == profile
        with app.state.container.database.transaction() as transaction:
            assert transaction.scalar(text("SELECT count(*) FROM project")) == 1
            assert transaction.scalar(text("SELECT count(*) FROM membership")) == 3


def test_nonmember_and_absent_projects_are_indistinguishable(integration_settings: Settings) -> None:
    mailer = FakeMailer()
    app = create_app(integration_settings, mailer=mailer)
    hidden_project = uuid4()
    with TestClient(app) as client:
        profile = login(client, mailer, unique_email("viewer")).json()
        with app.state.container.database.transaction() as transaction:
            transaction.execute(
                text("INSERT INTO project (id, name, is_shared_sample) VALUES (:id, :name, false)"),
                {"id": hidden_project, "name": "Private test project"},
            )
        hidden = client.get(f"/api/projects/{hidden_project}/participants")
        absent = client.get(f"/api/projects/{uuid4()}/participants")
        assert hidden.status_code == absent.status_code == 404
        assert hidden.json() == absent.json()
        assert hidden.json()["error"]["code"] == "NOT_FOUND"
        project_ids = {project["id"] for project in client.get("/api/projects").json()["items"]}
        assert project_ids == {profile["default_project_id"]}


def test_deleted_membership_revokes_participant_visibility(integration_settings: Settings) -> None:
    mailer = FakeMailer()
    app = create_app(integration_settings, mailer=mailer)
    with TestClient(app) as client:
        profile = login(client, mailer, unique_email("removed")).json()
        project_id = profile["default_project_id"]
        with app.state.container.database.transaction() as transaction:
            transaction.execute(
                text("DELETE FROM membership WHERE account_id = :account_id AND project_id = :project_id"),
                {"account_id": profile["account"]["id"], "project_id": project_id},
            )
        assert client.get("/api/projects").json() == {"items": []}
        assert client.get(f"/api/projects/{project_id}/participants").status_code == 404
