"""B7: a saved conclusion creates one authorized root conversation with a durable pinned input.

The shared database fixture migrates and drops only a disposable ramus_test_* database.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from login_flow import login, new_key, unique_email
from sqlalchemy import delete, insert, select, update

from ramus_api.main import create_app
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.resources.infrastructure.context_provider import build_context_provider
from ramus_api.orm_registry import metadata

pytestmark = pytest.mark.integration


@dataclass
class Followups:
    app: object
    owner: TestClient
    recipient: TestClient
    outsider: TestClient
    owner_id: UUID
    recipient_id: UUID
    source_project: UUID
    target_project: UUID
    result_id: UUID
    source_conversation: UUID
    resource_revision: UUID
    old_revision: UUID
    latest_revision: UUID

    def create(self, *, client=None, project=None, revision=None, title="후속 검토", key=None):
        return (client or self.owner).post(
            f"/api/projects/{project or self.target_project}/conversations/from-result",
            json={"result_revision_id": str(revision or self.old_revision), "title": title}, headers=key or new_key(),
        )


def rows(database, name, **conditions):
    table = metadata.tables[name]
    with database.transaction() as session:
        return list(session.execute(select(table).where(
            *(table.c[key] == value for key, value in conditions.items()),
        )).mappings())


@pytest.fixture
def followups(database, integration_settings):
    mailer = FakeMailer()
    app = create_app(integration_settings, mailer=mailer)
    with ExitStack() as stack:
        owner = stack.enter_context(TestClient(app, client=(f"b7-owner-{uuid4().hex}", 50000)))
        recipient = TestClient(app, client=(f"b7-recipient-{uuid4().hex}", 50001))
        outsider = TestClient(app, client=(f"b7-outsider-{uuid4().hex}", 50002))
        stack.callback(recipient.close)
        stack.callback(outsider.close)
        identities = [login(client, mailer, unique_email("followups")).json() for client in (owner, recipient, outsider)]
        owner_id, recipient_id, _ = [UUID(identity["account"]["id"]) for identity in identities]
        source, target, parent, child, task, run, result, old, latest, resource, resource_revision = (uuid4() for _ in range(11))
        tables = metadata.tables
        with database.transaction() as session:
            for project, name in ((source, "원본 기획"), (target, "구현 프로젝트")):
                session.execute(insert(tables["project"]).values(id=project, name=name))
            for project, account in ((source, owner_id), (target, owner_id), (target, recipient_id)):
                session.execute(insert(tables["membership"]).values(project_id=project, account_id=account, role="editor"))
            session.execute(insert(tables["conversation"]).values(
                id=parent, project_id=source, title="부모 대화", origin="top", created_by=owner_id,
            ))
            session.execute(insert(tables["conversation"]).values(
                id=child, project_id=source, parent_id=parent, task_id=task, title="원본 조사", origin="branch", created_by=owner_id,
            ))
            session.execute(insert(tables["run"]).values(
                id=run, project_id=source, conversation_id=parent, purpose="work", status="succeeded",
                requested_by=owner_id, credential_account_id=owner_id, input_snapshot={},
            ))
            session.execute(insert(tables["task"]).values(
                id=task, source_conversation_id=parent, child_conversation_id=child, source_run_id=run,
                ordinal=1, title="원본 조사", goal="조건 검토", status="ready", requested_by=owner_id,
            ))
            session.execute(insert(tables["resource"]).values(
                id=resource, project_id=source, kind="skill", latest_revision_id=resource_revision, created_by=owner_id,
            ))
            session.execute(insert(tables["resource_revision"]).values(
                id=resource_revision, resource_id=resource, number=1, name="비공개 기준", description="원본에 유지",
                instructions="복사하면 안 되는 스킬", content_hash="c" * 64, created_by=owner_id,
            ))
            session.execute(insert(tables["conversation_resource"]).values(
                conversation_id=child, resource_id=resource, revision_id=resource_revision, applied_by=owner_id,
            ))
            session.execute(insert(tables["result"]).values(
                id=result, project_id=source, source_conversation_id=child, source_task_id=task,
                title="최신 원본 제목", latest_revision_id=latest, latest_version=2,
            ))
            for revision, version, conclusion, title in (
                (old, 1, "검토한 첫 결론", "처음 저장한 결론"), (latest, 2, "나중에 수정한 결론", "최신 원본 제목"),
            ):
                session.execute(insert(tables["result_revision"]).values(
                    id=revision, result_id=result, version=version, title=title, conclusion=conclusion,
                    source={"conversation_id": str(child), "message_from_seq": 1, "message_to_seq": 2,
                            "resource_revision_ids": [str(resource_revision)], "input_result_revision_ids": [], "run_id": str(run)},
                    saved_by=owner_id,
                ))
        yield Followups(app, owner, recipient, outsider, owner_id, recipient_id,
                        source, target, result, child, resource_revision, old, latest)


@pytest.mark.parametrize("same_project", [False, True])
def test_exact_saved_version_creates_root_with_only_pinned_conclusion_and_no_ai(followups, database, same_project):
    fixture = followups
    project = fixture.source_project if same_project else fixture.target_project
    before_runs = len(rows(database, "run"))
    before_resources = len(rows(database, "resource"))
    original = rows(database, "result", id=fixture.result_id)[0]
    response = fixture.create(project=project)
    assert response.status_code == 200, response.text
    conversation = response.json()
    conversation_id = UUID(conversation["id"])
    assert conversation["project_id"] == str(project)
    assert conversation["parent_id"] is None and conversation["task_id"] is None and conversation["path"] == []
    assert conversation["created_by"] == str(fixture.owner_id)
    assert fixture.owner.get(f"/api/conversations/{conversation_id}").json()["active_run"] is None
    inputs = fixture.owner.get(f"/api/conversations/{conversation_id}/inputs")
    assert inputs.status_code == 200, inputs.text
    [item] = inputs.json()["items"]
    assert item["result_revision_id"] == str(fixture.old_revision) and item["version"] == 1
    assert item["latest_version"] == 2 and item["title"] == "처음 저장한 결론"
    assert item["origin"] == "new_conversation"
    [stored] = rows(database, "conversation_input", conversation_id=conversation_id)
    assert stored["conclusion_snapshot"] == "검토한 첫 결론"
    assert stored["source_snapshot"]["resource_revision_ids"] == [str(fixture.resource_revision)]
    assert not rows(database, "conversation_resource", conversation_id=conversation_id)
    assert not rows(database, "message", conversation_id=conversation_id)
    assert not rows(database, "share", target_conversation_id=conversation_id)
    assert len(rows(database, "run")) == before_runs
    assert len(rows(database, "resource")) == before_resources
    assert rows(database, "result", id=fixture.result_id)[0] == original
    with database.transaction() as session:
        context = build_context_provider().snapshot(session, conversation_id)
        assert context.resources == ()
        assert len(context.results) == 1
        assert context.results[0].result_revision_id == fixture.old_revision
        assert context.results[0].conclusion == "검토한 첫 결론"


def test_received_version_can_start_followup_without_source_access_or_latest_metadata(followups, database):
    fixture = followups
    assert fixture.create(client=fixture.recipient).status_code == 404
    created = fixture.create().json()
    assert fixture.recipient.get(f"/api/result-revisions/{fixture.old_revision}").status_code == 404
    assert fixture.recipient.get(f"/api/conversations/{fixture.source_conversation}").status_code == 404
    received = fixture.recipient.get(f"/api/conversations/{created['id']}/inputs").json()["items"]
    assert received[0]["latest_version"] == 1 and received[0]["title"] == "처음 저장한 결론"
    next_conversation = fixture.create(client=fixture.recipient)
    assert next_conversation.status_code == 200, next_conversation.text
    [snapshot] = rows(database, "conversation_input", conversation_id=UUID(next_conversation.json()["id"]))
    assert snapshot["result_revision_id"] == fixture.old_revision
    assert snapshot["conclusion_snapshot"] == "검토한 첫 결론"
    # Receiving one version cannot grant access to any later or unrelated version.
    assert fixture.create(client=fixture.recipient, revision=fixture.latest_revision).status_code == 404


def test_project_search_filters_permissions_and_creation_rechecks_them(followups, database):
    fixture = followups
    search = fixture.recipient.get("/api/projects/search", params={"q": "프로젝트"})
    assert search.status_code == 200
    assert str(fixture.target_project) in {project["id"] for project in search.json()["items"]}
    source_search = fixture.recipient.get("/api/projects/search", params={"q": "원본 기획"})
    assert source_search.json()["items"] == []
    created = fixture.create().json()
    key = new_key()
    accepted = fixture.create(client=fixture.recipient, key=key)
    assert accepted.status_code == 200
    with database.transaction() as session:
        table = metadata.tables["membership"]
        session.execute(delete(table).where(table.c.project_id == fixture.target_project,
                                           table.c.account_id == fixture.recipient_id))
    revoked = fixture.create(client=fixture.recipient, key=key)
    assert revoked.status_code == 403
    assert revoked.json()["error"]["code"] == "PROJECT_CREATE_FORBIDDEN"
    assert fixture.recipient.get(f"/api/conversations/{created['id']}/inputs").status_code == 404
    assert fixture.create(project=uuid4()).status_code == 403
    assert fixture.create(client=fixture.outsider).status_code == 403


def test_concurrent_retry_creates_one_conversation_and_publishes_two_events_once(followups, database):
    fixture = followups
    container = fixture.app.state.container
    subscription = fixture.owner.portal.call(container.events.subscribe, fixture.target_project)
    key = new_key()
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(fixture.create, key=key) for _ in range(4)]
            responses = [future.result(timeout=15) for future in futures]
        assert [response.status_code for response in responses] == [200] * 4
        assert all(response.json() == responses[0].json() for response in responses)
        conversation_id = UUID(responses[0].json()["id"])
        assert len(rows(database, "conversation_input", conversation_id=conversation_id)) == 1
        assert len(rows(database, "conversation", project_id=fixture.target_project)) == 1
        fixture.owner.portal.call(container.event_relay.flush)
        first = fixture.owner.portal.call(subscription.next, 0.2)
        second = fixture.owner.portal.call(subscription.next, 0.2)
        assert first.name == "conversation.created" and second.name == "conversation_inputs.updated"
        assert second.data["conversation_id"] == conversation_id
        assert fixture.recipient.get(f"/api/conversations/{conversation_id}/inputs").status_code == 200
        assert fixture.owner.portal.call(subscription.next, 0.01) is None
        assert fixture.create(key=key, title="다른 제목").status_code == 409
        assert fixture.create(key=key, revision=fixture.latest_revision).status_code == 409
    finally:
        fixture.owner.portal.call(subscription.close)


@pytest.mark.parametrize("title", ["", " \n\t", "x" * 101, "private\x00text"])
def test_invalid_titles_leave_no_conversation_or_snapshot(followups, database, title):
    fixture = followups
    response = fixture.create(title=title)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "INVALID_INPUT"
    assert not rows(database, "conversation", project_id=fixture.target_project)


def test_unsaved_revision_anonymous_requests_and_invalid_shapes_are_rejected(followups, database):
    fixture = followups
    assert fixture.create(revision=uuid4()).status_code == 404
    assert fixture.create(revision=fixture.result_id).status_code == 404
    path = f"/api/projects/{fixture.target_project}/conversations/from-result"
    assert fixture.owner.post(path, json={"result_revision_id": str(fixture.old_revision), "title": "okay", "parent_id": str(uuid4())}, headers=new_key()).status_code == 422
    anonymous = TestClient(fixture.app)
    try:
        assert fixture.create(client=anonymous).status_code == 401
        assert anonymous.get(f"/api/conversations/{fixture.source_conversation}/inputs").status_code == 401
    finally:
        anonymous.close()
    assert not rows(database, "conversation", project_id=fixture.target_project)


def test_snapshot_failure_rolls_back_conversation_receipt_and_events(followups, database, monkeypatch):
    fixture = followups
    from ramus_api.modules.sharing.infrastructure.inputs import SqlConversationInputs

    def fail(*_args):
        raise RuntimeError("test snapshot failure")

    key = new_key()
    with monkeypatch.context() as changes:
        changes.setattr(SqlConversationInputs, "add", fail)
        with pytest.raises(RuntimeError, match="test snapshot failure"):
            fixture.create(key=key)
    assert not rows(database, "conversation", project_id=fixture.target_project)
    assert not rows(database, "request_receipt", idempotency_key=key["Idempotency-Key"])
    retry = fixture.create(key=key)
    assert retry.status_code == 200, retry.text


def test_received_snapshot_stays_at_requested_version_after_new_approval(followups, database):
    fixture = followups
    created = fixture.create().json()
    with database.transaction() as session:
        result, revision = metadata.tables["result"], metadata.tables["result_revision"]
        source = session.execute(select(revision.c.source).where(revision.c.id == fixture.latest_revision)).scalar_one()
        newer = uuid4()
        session.execute(insert(revision).values(
            id=newer, result_id=fixture.result_id, version=3, title="후속 변경", conclusion="세 번째 원본 결론",
            source=source, saved_by=fixture.owner_id,
        ))
        session.execute(update(result).where(result.c.id == fixture.result_id).values(latest_revision_id=newer, latest_version=3))
    [item] = fixture.owner.get(f"/api/conversations/{created['id']}/inputs").json()["items"]
    assert item["version"] == 1 and item["latest_version"] == 3
    [stored] = rows(database, "conversation_input", conversation_id=UUID(created["id"]))
    assert stored["conclusion_snapshot"] == "검토한 첫 결론"
    again = fixture.create(client=fixture.recipient)
    assert again.status_code == 200 and again.json()["parent_id"] is None


def test_recipient_opens_exact_stored_input_without_original_access_or_side_effects(followups, database, monkeypatch):
    fixture = followups
    created = fixture.create().json()
    [item] = fixture.recipient.get(f"/api/conversations/{created['id']}/inputs").json()["items"]
    path = f"/api/conversations/{created['id']}/inputs/{item['id']}"
    tracked = ("conversation", "conversation_input", "share", "message", "run", "request_receipt")
    before = {table: len(rows(database, table)) for table in tracked}
    [stored] = rows(database, "conversation_input", id=UUID(item["id"]))

    # Even an adapter reading different original contents must not replace the received snapshot.
    from dataclasses import replace

    from ramus_api.modules.results.infrastructure.approved import SqlApprovedConclusionReader

    original = SqlApprovedConclusionReader.get

    def different_source(self, session, revision_id):
        revision = original(self, session, revision_id)
        return replace(revision, conclusion="원본 조회에서 온 다른 본문", title="노출하면 안 되는 원본 제목",
                       source={"conversation_id": str(uuid4())}) if revision else None

    monkeypatch.setattr(SqlApprovedConclusionReader, "get", different_source)
    opened = fixture.recipient.get(path)
    assert opened.status_code == 200, opened.text
    detail = opened.json()
    assert {key: detail[key] for key in item} == item
    assert detail["conclusion"] == "검토한 첫 결론"
    assert detail["source"] == stored["source_snapshot"]
    assert detail["latest_version"] == detail["version"] == 1
    assert detail["result_revision_id"] == str(fixture.old_revision)
    assert fixture.recipient.get(f"/api/conversations/{fixture.source_conversation}").status_code == 404
    assert fixture.recipient.get(f"/api/result-revisions/{fixture.old_revision}").status_code == 404
    assert fixture.recipient.get(f"/api/result-revisions/{fixture.latest_revision}").status_code == 404
    assert {table: len(rows(database, table)) for table in tracked} == before


def test_input_detail_checks_conversation_binding_current_membership_and_login(followups, database):
    fixture = followups
    first, second = fixture.create().json(), fixture.create().json()
    [item] = fixture.owner.get(f"/api/conversations/{first['id']}/inputs").json()["items"]
    path = f"/api/conversations/{first['id']}/inputs/{item['id']}"
    assert fixture.owner.get(path).status_code == 200
    assert fixture.owner.get(path).json()["latest_version"] == 2
    assert fixture.owner.get(f"/api/conversations/{second['id']}/inputs/{item['id']}").status_code == 404
    assert fixture.owner.get(f"/api/conversations/{fixture.source_conversation}/inputs/{item['id']}").status_code == 404
    assert fixture.owner.get(f"/api/conversations/{first['id']}/inputs/{uuid4()}").status_code == 404
    assert fixture.owner.get(f"/api/conversations/{first['id']}/inputs/{fixture.latest_revision}").status_code == 404
    assert fixture.outsider.get(path).status_code == 404
    anonymous = TestClient(fixture.app)
    try:
        assert anonymous.get(path).status_code == 401
    finally:
        anonymous.close()
    with database.transaction() as session:
        membership = metadata.tables["membership"]
        session.execute(delete(membership).where(membership.c.project_id == fixture.target_project,
                                                membership.c.account_id == fixture.recipient_id))
    assert fixture.recipient.get(path).status_code == 404
