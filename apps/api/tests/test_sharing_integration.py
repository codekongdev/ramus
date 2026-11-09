"""B6 uses the real transactional API and a disposable PostgreSQL database, never real AI."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from login_flow import error_code, login, new_key, unique_email
from sqlalchemy import delete, insert, select

from ramus_api.main import create_app
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.execution.domain.snapshot import EMPTY_SNAPSHOT, snapshot_to_json
from ramus_api.modules.execution.fakes.llm import FakeLLM
from ramus_api.modules.realtime.domain.events import EventName
from ramus_api.modules.sharing.infrastructure.repository import SqlSharingRepository
from ramus_api.orm_registry import metadata
from ramus_api.shared.domain.primitives import utc_now

pytestmark = pytest.mark.integration


@dataclass
class Fixture:
    app: object
    owner: TestClient
    editor: TestClient
    outsider: TestClient
    actor_id: UUID
    project_id: UUID
    source_id: UUID
    target_ids: tuple[UUID, UUID]
    other_project_target: UUID
    result_id: UUID
    revision_ids: tuple[UUID, UUID]
    source: dict
    gateway: FakeLLM

    def send(self, version=1, targets=None, *, client=None, headers=None):
        return (client or self.owner).post(f"/api/result-revisions/{self.revision_ids[version - 1]}/shares",
            json={"conversation_ids": [str(item) for item in (self.target_ids if targets is None else targets)]},
            headers=headers or new_key())

    def inputs(self, target=None, *, client=None):
        return (client or self.owner).get(f"/api/conversations/{target or self.target_ids[0]}/inputs")


def rows(database, table_name, **conditions):
    table = metadata.tables[table_name]
    with database.transaction() as session:
        return [dict(row) for row in session.execute(select(table).where(
            *(table.c[key] == value for key, value in conditions.items())
        )).mappings()]


@pytest.fixture
def sharing_fixture(database, integration_settings):
    gateway, mailer = FakeLLM(), FakeMailer()
    app = create_app(integration_settings, mailer=mailer, llm_gateway=gateway)
    clients = [TestClient(app, client=(f"sharing-{uuid4().hex}", 51000)) for _ in range(3)]
    owner, editor, outsider = [UUID(login(client, mailer, unique_email("sharing")).json()["account"]["id"])
                              for client in clients]
    project, other_project, parent, source, task, run, target1, target2, foreign, result, v1, v2 = (
        uuid4() for _ in range(12)
    )
    tables = metadata.tables
    source_data = dict(conversation_id=str(source), message_from_seq=1, message_to_seq=2,
                       resource_revision_ids=[], input_result_revision_ids=[], run_id=str(run))
    with database.transaction() as session:
        for identifier in (project, other_project):
            session.execute(insert(tables["project"]).values(id=identifier, name="공유 검증 프로젝트"))
            for actor in (owner, editor):
                session.execute(insert(tables["membership"]).values(
                    project_id=identifier, account_id=actor, role="editor",
                ))
        for identifier, project_id, title in ((parent, project, "원래 논의"), (target1, project, "통합 구성안"),
                                               (target2, project, "통합 구성안"), (foreign, other_project, "다른 프로젝트")):
            session.execute(insert(tables["conversation"]).values(
                id=identifier, project_id=project_id, title=title, origin="top", created_by=owner,
            ))
        session.execute(insert(tables["conversation"]).values(
            id=source, project_id=project, parent_id=parent, task_id=task,
            title="공유할 조사", origin="branch", created_by=owner,
        ))
        session.execute(insert(tables["run"]).values(
            id=run, project_id=project, conversation_id=parent, status="succeeded", purpose="work",
            requested_by=owner, credential_account_id=owner, input_snapshot=snapshot_to_json(EMPTY_SNAPSHOT),
        ))
        session.execute(insert(tables["task"]).values(
            id=task, source_conversation_id=parent, child_conversation_id=source, source_run_id=run,
            ordinal=1, title="공유할 조사", goal="정책 조사", status="ready", requested_by=owner,
        ))
        session.execute(insert(tables["result"]).values(
            id=result, project_id=project, source_conversation_id=source, source_task_id=task,
            title="조사 결론", latest_revision_id=v2, latest_version=2,
        ))
        for version, identifier in enumerate((v1, v2), start=1):
            session.execute(insert(tables["result_revision"]).values(
                id=identifier, result_id=result, version=version, title=f"조사 결론 v{version}",
                conclusion=f"검토한 결론 버전 {version}", source=source_data, saved_by=owner,
            ))
        session.execute(insert(tables["ai_connection"]).values(
            account_id=owner, provider="openai", ciphertext="fixture-only", status="connected", verified_at=utc_now(),
        ))
    yield Fixture(app, *clients, owner, project, source, (target1, target2), foreign, result, (v1, v2), source_data, gateway)
    for client in clients:
        client.close()
    app.state.container.database.dispose()


@pytest.mark.asyncio
async def test_multi_send_is_atomic_pinned_idempotent_and_does_not_run_ai(sharing_fixture, database):
    fixture = sharing_fixture
    container = fixture.app.state.container
    await container.event_relay.flush()
    subscription = container.events.subscribe(fixture.project_id)
    key = new_key()
    before_runs = len(rows(database, "run", project_id=fixture.project_id))
    sent = fixture.send(headers=key)
    assert sent.status_code == 200, sent.text
    assert [item["outcome"] for item in sent.json()["items"]] == ["linked", "linked"]
    assert fixture.send(headers=key).json() == sent.json()
    assert [item["outcome"] for item in fixture.send().json()["items"]] == ["unchanged", "unchanged"]
    assert len(rows(database, "share", result_revision_id=fixture.revision_ids[0])) == 2
    assert len(rows(database, "run", project_id=fixture.project_id)) == before_runs
    assert fixture.gateway.calls == ()
    for target in fixture.target_ids:
        item = fixture.inputs(target).json()["items"][0]
        assert item["result_id"] == str(fixture.result_id)
        assert item["result_revision_id"] == str(fixture.revision_ids[0])
        assert item["version"] == 1 and item["latest_version"] == 2
        assert item["title"] == "조사 결론 v1" and item["origin"] == "share"
        stored = rows(database, "conversation_input", conversation_id=target, result_id=fixture.result_id)[0]
        assert stored["conclusion_snapshot"] == "검토한 결론 버전 1"
        assert stored["source_snapshot"] == fixture.source
    await container.event_relay.flush()
    events = [await subscription.next(0.1), await subscription.next(0.1)]
    assert {event.data["conversation_id"] for event in events} == set(fixture.target_ids)
    assert all(event.name == EventName.CONVERSATION_INPUTS_UPDATED for event in events)
    assert all(set(event.data) == {"conversation_id"} for event in events)
    assert await subscription.next(0.01) is None
    subscription.close()


def test_resend_new_version_replaces_and_old_version_cannot_downgrade(sharing_fixture, database):
    fixture = sharing_fixture
    assert fixture.send().status_code == 200
    original = fixture.inputs().json()["items"][0]
    # Opening an immutable revision and the received list never changes the current input.
    assert fixture.owner.get(f"/api/result-revisions/{fixture.revision_ids[1]}").status_code == 200
    assert fixture.inputs().json()["items"][0] == original
    replaced = fixture.send(2)
    assert [item["outcome"] for item in replaced.json()["items"]] == ["replaced", "replaced"]
    latest = fixture.inputs().json()["items"][0]
    assert latest["id"] == original["id"] and latest["version"] == 2
    assert latest["result_revision_id"] == str(fixture.revision_ids[1])
    assert latest["created_at"] == original["created_at"]
    assert [item["outcome"] for item in fixture.send(1).json()["items"]] == ["kept_newer", "kept_newer"]
    assert fixture.inputs().json()["items"][0] == latest
    assert len(rows(database, "conversation_input", result_id=fixture.result_id)) == 2
    assert len(rows(database, "share", result_revision_id=fixture.revision_ids[0])) == 2
    assert len(rows(database, "share", result_revision_id=fixture.revision_ids[1])) == 2


@pytest.mark.parametrize("case,code,status", [
    ("empty", "SHARE_TARGET_INVALID", 422), ("duplicate", "SHARE_TARGET_INVALID", 422),
    ("self", "SHARE_TARGET_INVALID", 422), ("other_project", "SHARE_TARGET_INVALID", 422),
    ("missing", "NOT_FOUND", 404), ("inaccessible", "NOT_FOUND", 404),
])
def test_invalid_batch_never_partially_writes(sharing_fixture, database, case, code, status):
    fixture = sharing_fixture
    targets = {
        "empty": (), "duplicate": (fixture.target_ids[0], fixture.target_ids[0]),
        "self": (fixture.target_ids[0], fixture.source_id),
        "other_project": (fixture.target_ids[0], fixture.other_project_target),
        "missing": (fixture.target_ids[0], uuid4()), "inaccessible": fixture.target_ids,
    }[case]
    response = fixture.send(targets=targets, client=fixture.outsider if case == "inaccessible" else None)
    assert response.status_code == status, response.text
    assert error_code(response) == code
    assert not rows(database, "conversation_input", result_id=fixture.result_id)
    assert not rows(database, "share", result_revision_id=fixture.revision_ids[0])


def test_inputs_and_saved_source_require_membership_and_login(sharing_fixture):
    fixture = sharing_fixture
    assert fixture.inputs(client=fixture.outsider).status_code == 404
    assert fixture.inputs(uuid4()).status_code == 404
    missing = fixture.owner.post(f"/api/result-revisions/{uuid4()}/shares",
                                json={"conversation_ids": [str(fixture.target_ids[0])]}, headers=new_key())
    assert missing.status_code == 404
    anonymous = TestClient(fixture.app)
    try:
        assert fixture.inputs(client=anonymous).status_code == 401
        assert fixture.send(client=anonymous).status_code == 401
    finally:
        anonymous.close()
    # No key means authentication is not needed to detect the malformed mutation envelope.
    no_key = fixture.owner.post(f"/api/result-revisions/{fixture.revision_ids[0]}/shares",
                               json={"conversation_ids": []})
    assert no_key.status_code == 400 and error_code(no_key) == "IDEMPOTENCY_KEY_INVALID"
    assert fixture.inputs().json() == {"items": []}


def test_replay_rechecks_membership_and_conflicting_payload_is_rejected(sharing_fixture, database):
    fixture = sharing_fixture
    key = new_key()
    sent = fixture.send(headers=key)
    assert sent.status_code == 200
    conflict = fixture.send(targets=(fixture.target_ids[0],), headers=key)
    assert conflict.status_code == 409 and error_code(conflict) == "IDEMPOTENCY_CONFLICT"
    with database.transaction() as session:
        membership = metadata.tables["membership"]
        session.execute(delete(membership).where(membership.c.project_id == fixture.project_id,
                                                membership.c.account_id == fixture.actor_id))
    assert fixture.send(headers=key).status_code == 404
    assert fixture.inputs().status_code == 404


@pytest.mark.asyncio
async def test_second_target_failure_rolls_back_history_inputs_receipt_and_events(sharing_fixture, database, monkeypatch):
    fixture = sharing_fixture
    container = fixture.app.state.container
    await container.event_relay.flush()
    subscription = container.events.subscribe(fixture.project_id)
    pin = SqlSharingRepository.pin
    calls = 0

    def fail_second(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected local database failure")
        return pin(self, *args, **kwargs)

    monkeypatch.setattr(SqlSharingRepository, "pin", fail_second)
    with pytest.raises(RuntimeError, match="injected local database failure"):
        fixture.send()
    assert not rows(database, "share", result_revision_id=fixture.revision_ids[0])
    assert not rows(database, "conversation_input", result_id=fixture.result_id)
    assert not rows(database, "request_receipt", scope=f"sharing.send:{fixture.revision_ids[0]}")
    await container.event_relay.flush()
    assert await subscription.next(0.01) is None
    subscription.close()


def test_concurrent_versions_never_duplicate_or_downgrade(sharing_fixture, database):
    fixture = sharing_fixture
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(fixture.send, version, (fixture.target_ids[0],), client=client)
                   for version, client in ((1, fixture.owner), (2, fixture.editor))]
        responses = [future.result(timeout=10) for future in futures]
    assert all(response.status_code == 200 for response in responses), [r.text for r in responses]
    assert fixture.inputs().json()["items"][0]["version"] == 2
    assert len(rows(database, "conversation_input", conversation_id=fixture.target_ids[0], result_id=fixture.result_id)) == 1
    assert len(rows(database, "share", target_conversation_id=fixture.target_ids[0])) == 2


@pytest.mark.asyncio
async def test_next_ai_uses_the_sent_snapshot_and_records_the_same_revision(sharing_fixture, database):
    fixture = sharing_fixture
    assert fixture.send().status_code == 200
    assert fixture.gateway.calls == ()
    requested = fixture.owner.post(f"/api/conversations/{fixture.target_ids[0]}/messages",
        json={"body": "@AI 받은 결론으로 구성안을 만들어 주세요."}, headers=new_key())
    assert requested.status_code == 200, requested.text
    run_id = UUID(requested.json()["run"]["id"])
    worker = fixture.app.state.container.execution_runtime.worker
    # The session-scoped disposable database also contains pending runs left by earlier tests.
    # Production claims globally in creation order, so one iteration need not be our request.
    # Bound progress by the queue present now; do not cancel or delete another test's records.
    pending_count = len(rows(database, "run", status="pending"))
    for _ in range(pending_count):
        assert await worker.run_once(), "The requested pending run must remain claimable"
        stored_run = rows(database, "run", id=run_id)[0]
        if stored_run["status"] != "pending":
            break
    assert stored_run["id"] == run_id
    assert stored_run["conversation_id"] == fixture.target_ids[0]
    assert stored_run["status"] == "succeeded", stored_run
    request = fixture.gateway.calls[-1]
    assert request.credential_account_id == fixture.actor_id
    assert "@AI 받은 결론으로 구성안을 만들어 주세요." in request.messages[-1].content
    assert [item.result_revision_id for item in request.context.results] == [fixture.revision_ids[0]]
    assert request.context.results[0].conclusion == "검토한 결론 버전 1"
    assert stored_run["input_snapshot"]["input_result_revision_ids"] == [str(fixture.revision_ids[0])]


def test_project_graph_reflects_branches_task_status_and_pinned_usage(sharing_fixture, database):
    fixture = sharing_fixture
    path = f"/api/projects/{fixture.project_id}/graph"
    before = fixture.owner.get(path)
    assert before.status_code == 200
    graph = before.json()
    nodes = {node["conversation_id"]: node for node in graph["nodes"]}
    source = nodes[str(fixture.source_id)]
    assert source["task_status"] == "ready"
    assert source["parent_id"] in nodes
    assert graph["edges"] == [{"kind": "branch", "from": source["parent_id"], "to": str(fixture.source_id)}]
    assert fixture.outsider.get(path).status_code == 404
    assert fixture.owner.get(f"/api/projects/{uuid4()}/graph").status_code == 404
    anonymous = TestClient(fixture.app)
    try:
        assert anonymous.get(path).status_code == 401
    finally:
        anonymous.close()

    assert fixture.send().status_code == 200
    assert fixture.send(2).status_code == 200
    graph = fixture.owner.get(path).json()
    uses = [edge for edge in graph["edges"] if edge["kind"] == "uses_result"]
    assert {edge["to"] for edge in uses} == {str(target) for target in fixture.target_ids}
    assert all(edge["from"] == str(fixture.source_id) for edge in uses)
    assert len(uses) == 2  # resending a different revision does not duplicate a relationship

    followup = fixture.owner.post(
        f"/api/projects/{fixture.project_id}/conversations/from-result",
        json={"result_revision_id": str(fixture.revision_ids[0]), "title": "후속 대화"}, headers=new_key(),
    )
    assert followup.status_code == 200, followup.text
    followup_id = followup.json()["id"]
    graph = fixture.owner.get(path).json()
    assert {"kind": "uses_result", "from": str(fixture.source_id), "to": followup_id} in graph["edges"]
    assert next(node for node in graph["nodes"] if node["conversation_id"] == followup_id)["parent_id"] is None

    with database.transaction() as session:
        other_project = session.scalar(select(metadata.tables["conversation"].c.project_id).where(
            metadata.tables["conversation"].c.id == fixture.other_project_target,
        ))
    cross_project = fixture.owner.post(
        f"/api/projects/{other_project}/conversations/from-result",
        json={"result_revision_id": str(fixture.revision_ids[0]), "title": "다른 프로젝트 대화"},
        headers=new_key(),
    )
    assert cross_project.status_code == 200, cross_project.text
    other_graph = fixture.owner.get(f"/api/projects/{other_project}/graph").json()
    assert all(edge["from"] != str(fixture.source_id) for edge in other_graph["edges"])

    with database.transaction() as session:
        session.execute(metadata.tables["task"].update().where(
            metadata.tables["task"].c.child_conversation_id == fixture.source_id,
        ).values(status="failed"))
        session.execute(delete(metadata.tables["membership"]).where(
            metadata.tables["membership"].c.project_id == fixture.project_id,
            metadata.tables["membership"].c.account_id == fixture.actor_id,
        ))
    assert fixture.owner.get(path).status_code == 404
    refreshed = fixture.editor.get(path).json()
    assert next(node for node in refreshed["nodes"] if node["conversation_id"] == str(fixture.source_id))["task_status"] == "failed"
