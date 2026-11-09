"""B8 lists only approved heads within the authenticated project's boundary.

The shared fixture creates and migrates a disposable database, never development data.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from login_flow import error_code, login, new_key, unique_email
from sqlalchemy import delete, insert, update

from ramus_api.main import create_app
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.execution.domain.snapshot import EMPTY_SNAPSHOT, snapshot_to_json
from ramus_api.orm_registry import metadata

pytestmark = pytest.mark.integration
SAVED_AT = datetime(2026, 11, 9, 1, 0, tzinfo=UTC)


@dataclass
class Fixture:
    client: TestClient
    outsider: TestClient
    anonymous: TestClient
    account_id: UUID
    project_id: UUID

    def list(self, project_id=None, client=None):
        return (client or self.client).get(f"/api/projects/{project_id or self.project_id}/results")


@pytest.fixture
def results_fixture(integration_settings):
    mailer = FakeMailer()
    app = create_app(integration_settings, mailer=mailer)
    clients = [TestClient(app, client=(f"b8-{uuid4().hex}", 50000)) for _ in range(3)]
    identity = login(clients[0], mailer, unique_email("results-owner")).json()
    login(clients[1], mailer, unique_email("results-outsider"))
    project = clients[0].post("/api/projects", json={"name": "저장된 결과물 검증"}, headers=new_key())
    assert project.status_code == 200, project.text
    yield Fixture(*clients, UUID(identity["account"]["id"]), UUID(project.json()["id"]))
    for client in clients:
        client.close()
    app.state.container.database.dispose()


def add_result(database, fixture, *, project_id=None, versions=0, saved_at=SAVED_AT, draft_status=None):
    """Set up a task with immutable approvals and an optional newer, unsaved draft."""
    project_id = project_id or fixture.project_id
    parent, child, task, run, result = (uuid4() for _ in range(5))
    revisions = [uuid4() for _ in range(versions)]
    tables = metadata.tables
    with database.transaction() as session:
        session.execute(insert(tables["conversation"]).values(
            id=parent, project_id=project_id, title="원래 논의", origin="top", created_by=fixture.account_id,
        ))
        session.execute(insert(tables["conversation"]).values(
            id=child, project_id=project_id, parent_id=parent, task_id=task,
            title="출처 조사 대화", origin="branch", created_by=fixture.account_id,
        ))
        session.execute(insert(tables["run"]).values(
            id=run, project_id=project_id, conversation_id=parent, purpose="work", status="succeeded",
            requested_by=fixture.account_id, credential_account_id=fixture.account_id,
            input_snapshot=snapshot_to_json(EMPTY_SNAPSHOT),
        ))
        session.execute(insert(tables["task"]).values(
            id=task, source_conversation_id=parent, child_conversation_id=child, source_run_id=run,
            ordinal=1, title="결과 정리할 작업", goal="조사", status="ready", requested_by=fixture.account_id,
        ))
        session.execute(insert(tables["result"]).values(
            id=result, project_id=project_id, source_conversation_id=child, source_task_id=task,
            title="아직 저장하지 않은 제목", latest_version=versions,
            latest_revision_id=revisions[-1] if revisions else None,
        ))
        for version, revision in enumerate(revisions, 1):
            session.execute(insert(tables["result_revision"]).values(
                id=revision, result_id=result, version=version, title=f"승인된 결론 v{version}",
                conclusion=f"저장한 결론 {version}", saved_by=fixture.account_id,
                created_at=saved_at - timedelta(days=versions - version),
                source={"conversation_id": str(child), "message_from_seq": 1, "message_to_seq": 1,
                        "resource_revision_ids": [], "input_result_revision_ids": [], "run_id": str(run)},
            ))
        if draft_status is not None:
            session.execute(insert(tables["result_draft"]).values(
                result_id=result, status=draft_status, conclusion="아직 승인하지 않은 초안" if draft_status == "ready" else None,
                base_version=versions, run_id=run, message_from_seq=1, message_to_seq=1,
                context_snapshot={"resources": [], "results": []}, updated_at=saved_at + timedelta(days=10),
                error_code="LLM_UNAVAILABLE" if draft_status == "failed" else None,
            ))
    return result, revisions, run


def test_result_listing_requires_login(results_fixture):
    response = results_fixture.list(client=results_fixture.anonymous)
    assert response.status_code == 401
    assert error_code(response) == "UNAUTHORIZED"


def test_result_listing_returns_empty_project(results_fixture):
    response = results_fixture.list()
    assert response.status_code == 200
    assert response.json() == {"items": []}


@pytest.mark.parametrize("status", ["generating", "ready", "failed"])
def test_result_listing_excludes_unsaved_drafts(results_fixture, database, status):
    add_result(database, results_fixture, draft_status=status)
    assert results_fixture.list().json() == {"items": []}


@pytest.mark.parametrize("status", ["generating", "ready", "failed"])
def test_result_listing_keeps_approved_head_when_newer_draft_exists(results_fixture, database, status):
    result_id, revisions, _ = add_result(database, results_fixture, versions=2, draft_status=status)
    response = results_fixture.list()
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [{
        "result_id": str(result_id), "title": "승인된 결론 v2", "latest_version": 2,
        "latest_revision_id": str(revisions[1]), "source_conversation_title": "출처 조사 대화",
        "updated_at": SAVED_AT.isoformat().replace("+00:00", "Z"),
    }]}


def test_result_listing_is_project_scoped_and_sorted_by_approved_time(results_fixture, database):
    fixture = results_fixture
    other_project = fixture.client.post("/api/projects", json={"name": "다른 프로젝트"}, headers=new_key()).json()["id"]
    add_result(database, fixture, project_id=UUID(other_project), versions=1, saved_at=SAVED_AT + timedelta(days=2))
    first, _, _ = add_result(database, fixture, versions=1, saved_at=SAVED_AT)
    tied, _, _ = add_result(database, fixture, versions=1, saved_at=SAVED_AT)
    newest, _, _ = add_result(database, fixture, versions=1, saved_at=SAVED_AT + timedelta(days=1))
    items = fixture.list().json()["items"]
    assert [item["result_id"] for item in items] == [str(newest), *map(str, sorted((first, tied)))]
    assert fixture.list().json()["items"] == items
    assert len(fixture.list(project_id=other_project).json()["items"]) == 1


def test_result_listing_rechecks_membership_and_hides_unknown_projects(results_fixture, database):
    fixture = results_fixture
    add_result(database, fixture, versions=1)
    assert fixture.list().status_code == 200
    for response in (fixture.list(client=fixture.outsider), fixture.list(project_id=uuid4())):
        assert response.status_code == 404
        assert error_code(response) == "NOT_FOUND"
    with database.transaction() as session:
        member = metadata.tables["membership"]
        session.execute(delete(member).where(
            member.c.project_id == fixture.project_id, member.c.account_id == fixture.account_id,
        ))
    response = fixture.list()
    assert response.status_code == 404
    assert error_code(response) == "NOT_FOUND"


def test_approval_publishes_the_new_head_and_source_uses_current_conversation_title(results_fixture, database):
    fixture = results_fixture
    result_id, _, run_id = add_result(database, fixture, draft_status="ready")
    assert fixture.list().json() == {"items": []}
    saved = fixture.client.post(f"/api/results/{result_id}/revisions", json={
        "base_version": 0, "conclusion": "검토하고 승인한 결론", "source_run_id": str(run_id),
    }, headers=new_key())
    assert saved.status_code == 200, saved.text
    revision = saved.json()
    item = fixture.list().json()["items"][0]
    assert item["latest_revision_id"] == revision["id"]
    assert item["latest_version"] == revision["version"] == 1
    assert item["updated_at"] == revision["created_at"]
    with database.transaction() as session:
        conversation = metadata.tables["conversation"]
        session.execute(update(conversation).where(
            conversation.c.id == UUID(revision["source"]["conversation_id"]),
        ).values(title="수정한 출처 대화 제목"))
    assert fixture.list().json()["items"][0] == {**item, "source_conversation_title": "수정한 출처 대화 제목"}
