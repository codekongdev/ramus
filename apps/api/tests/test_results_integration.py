"""B4 exercises the real worker, durable snapshots, immutable approvals, and concurrent saves.

All database changes use the repository fixture's disposable test database, never development data.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from login_flow import error_code, login, new_key, unique_email
from sqlalchemy import delete, insert, select, update

from ramus_api.main import create_app
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.execution.domain.models import RunPurpose
from ramus_api.modules.execution.domain.snapshot import EMPTY_SNAPSHOT, snapshot_to_json
from ramus_api.modules.execution.fakes.llm import FakeLLM
from ramus_api.modules.results.domain.summary_chunks import SummaryLimits, input_size
from ramus_api.orm_registry import metadata
from ramus_api.shared.domain.primitives import utc_now

pytestmark = pytest.mark.integration


@dataclass
class Fixture:
    app: object
    client: TestClient
    editor: TestClient
    outsider: TestClient
    account_id: UUID
    editor_id: UUID
    project_id: UUID
    conversation_id: UUID
    task_id: UUID
    gateway: FakeLLM

    def summary(self, client=None, headers=None):
        return (client or self.client).post(f"/api/tasks/{self.task_id}/summaries", json={}, headers=headers or new_key())

    def result(self, result_id):
        response = self.client.get(f"/api/results/{result_id}")
        assert response.status_code == 200, response.text
        return response.json()

    def save(self, result_id, run_id, version=0, conclusion="검토한 결론", client=None, headers=None):
        return (client or self.client).post(
            f"/api/results/{result_id}/revisions",
            json={"base_version": version, "conclusion": conclusion, "source_run_id": str(run_id)},
            headers=headers or new_key(),
        )


def table_rows(database, name, **conditions):
    table = metadata.tables[name]
    with database.transaction() as session:
        return [dict(row) for row in session.execute(select(table).where(
            *(table.c[key] == value for key, value in conditions.items())
        )).mappings()]


@pytest.fixture
def summary_fixture(database, integration_settings):
    mailer, gateway = FakeMailer(), FakeLLM(summary_json='{"conclusion":"여러 메시지에서 도출한 결론입니다."}')
    app = create_app(integration_settings, mailer=mailer, llm_gateway=gateway)
    clients = [TestClient(app, client=(f"b4-{uuid4().hex}", 50000)) for _ in range(3)]
    identities = [login(client, mailer, unique_email("summary")).json() for client in clients]
    owner, editor, outsider = [UUID(identity["account"]["id"]) for identity in identities]
    project, parent, child, task, source_run = (uuid4() for _ in range(5))
    tables = metadata.tables
    with database.transaction() as session:
        run = tables["run"]
        session.execute(update(run).where(run.c.status.in_(("pending", "running"))).values(status="cancelled"))
        session.execute(insert(tables["project"]).values(id=project, name="결과 정리 검증"))
        for account in (owner, editor):
            session.execute(insert(tables["membership"]).values(account_id=account, project_id=project, role="editor"))
            session.execute(insert(tables["ai_connection"]).values(
                account_id=account, provider="openai", ciphertext="fixture-only-ciphertext", status="connected", verified_at=utc_now(),
            ))
        session.execute(insert(tables["conversation"]).values(
            id=parent, project_id=project, title="부모", origin="top", created_by=owner,
        ))
        session.execute(insert(tables["conversation"]).values(
            id=child, project_id=project, parent_id=parent, task_id=task, title="멤버십 조사", origin="branch", created_by=owner,
        ))
        session.execute(insert(tables["run"]).values(
            id=source_run, project_id=project, conversation_id=parent, purpose="work", status="succeeded",
            requested_by=owner, credential_account_id=owner, input_snapshot=snapshot_to_json(EMPTY_SNAPSHOT),
        ))
        session.execute(insert(tables["task"]).values(
            id=task, source_conversation_id=parent, child_conversation_id=child, source_run_id=source_run,
            ordinal=1, title="멤버십 조사", goal="가입·혜택 정책 비교", status="ready", requested_by=owner,
        ))
        for body in ("가입 조건을 조사해 주세요.", "가입은 무료이며 혜택은 조건부입니다."):
            session.execute(insert(tables["message"]).values(
                id=uuid4(), conversation_id=child, author_kind="ai", body=body,
            ))
    yield Fixture(app, *clients, owner, editor, project, child, task, gateway)
    for client in clients:
        client.close()
    app.state.container.database.dispose()


def add_message(database, fixture, body):
    message = metadata.tables["message"]
    with database.transaction() as session:
        return session.execute(insert(message).values(
            id=uuid4(), conversation_id=fixture.conversation_id, author_kind="ai", body=body,
        ).returning(message.c.seq)).scalar_one()


def pin_resource(database, fixture):
    resource, revision1, revision2 = (uuid4() for _ in range(3))
    tables = metadata.tables
    with database.transaction() as session:
        session.execute(insert(tables["resource"]).values(
            id=resource, project_id=fixture.project_id, kind="skill", latest_revision_id=revision2, created_by=fixture.account_id,
        ))
        for number, revision in ((1, revision1), (2, revision2)):
            session.execute(insert(tables["resource_revision"]).values(
                id=revision, resource_id=resource, number=number, name="조사 기준", description="버전 고정 검증",
                instructions=f"고정 지침 {number}", content_hash=str(number) * 64,
                base_revision_id=revision1 if number == 2 else None, created_by=fixture.account_id,
            ))
        session.execute(insert(tables["conversation_resource"]).values(
            conversation_id=fixture.conversation_id, resource_id=resource, revision_id=revision1, applied_by=fixture.account_id,
        ))
    return revision1, revision2


@pytest.mark.asyncio
async def test_summary_runs_once_with_request_time_scope_and_metadata(summary_fixture, database):
    fixture = summary_fixture
    revision1, revision2 = pin_resource(database, fixture)
    headers = new_key()
    first = fixture.summary(client=fixture.editor, headers=headers)
    assert first.status_code == 200, first.text
    result_id, draft = first.json()["id"], first.json()["draft"]
    assert draft["status"] == "generating" and draft["base_version"] == 0
    assert fixture.summary(client=fixture.editor, headers=headers).json() == first.json()
    assert fixture.summary().json()["draft"]["run_id"] == draft["run_id"]
    late_seq = add_message(database, fixture, "정리 요청 뒤 도착한 메시지는 제외합니다.")
    with database.transaction() as session:
        pin = metadata.tables["conversation_resource"]
        session.execute(update(pin).where(pin.c.conversation_id == fixture.conversation_id).values(revision_id=revision2))
    assert await fixture.app.state.container.execution_runtime.worker.run_once()
    assert len(fixture.gateway.calls) == 1
    request = fixture.gateway.calls[0]
    assert request.purpose == RunPurpose.SUMMARY
    assert request.credential_account_id == fixture.editor_id
    assert [item.revision_id for item in request.context.resources] == [revision1]
    assert request.message_to_seq < late_seq
    assert "정리 요청 뒤" not in request.messages[-1].content
    ready = fixture.result(result_id)
    assert ready["draft"]["status"] == "ready" and ready["latest_version"] is None
    saved_headers = new_key()
    saved = fixture.save(result_id, draft["run_id"], headers=saved_headers)
    assert saved.status_code == 200, saved.text
    assert fixture.save(result_id, draft["run_id"], headers=saved_headers).json() == saved.json()
    revision = saved.json()
    assert revision["version"] == 1 and revision["conclusion"] == "검토한 결론"
    assert revision["source"]["resource_revision_ids"] == [str(revision1)]
    assert revision["source"]["message_to_seq"] == request.message_to_seq
    run = table_rows(database, "run", id=UUID(draft["run_id"]))[0]
    assert run["input_snapshot"]["resource_revision_ids"] == [str(revision1)]
    assert run["requested_by"] == fixture.editor_id == run["credential_account_id"]
    assert fixture.result(result_id)["draft"] is None
    assert fixture.client.get(f"/api/result-revisions/{revision['id']}").json() == revision
    assert len(table_rows(database, "result_revision", result_id=UUID(result_id))) == 1
    assert table_rows(database, "task", id=fixture.task_id)[0]["status"] == "ready"


@pytest.mark.asyncio
async def test_resummary_uses_previous_approved_conclusion_and_new_messages_and_keeps_v1_on_failure(summary_fixture, database):
    fixture = summary_fixture
    created = fixture.summary().json()
    result_id, run_id = created["id"], created["draft"]["run_id"]
    await fixture.app.state.container.execution_runtime.worker.run_once()
    v1 = fixture.save(result_id, run_id).json()
    new_seq = add_message(database, fixture, "새로운 해지 조건을 조사했습니다.")
    updated = fixture.summary().json()
    await fixture.app.state.container.execution_runtime.worker.run_once()
    request = fixture.gateway.calls[-1]
    assert "검토한 결론" in request.messages[-1].content
    assert "새로운 해지 조건" in request.messages[-1].content
    assert "가입은 무료" not in request.messages[-1].content
    assert request.message_to_seq == new_seq
    assert v1["id"] in [str(item.result_revision_id) for item in request.context.results]
    v2 = fixture.save(result_id, updated["draft"]["run_id"], version=1, conclusion="업데이트 승인 결론")
    assert v2.status_code == 200, v2.text
    assert v2.json()["version"] == 2
    original = fixture.client.get(f"/api/result-revisions/{v1['id']}")
    assert original.json() == v1
    fixture.summary()
    fixture.gateway._failure_code = "LLM_UNAVAILABLE"
    await fixture.app.state.container.execution_runtime.worker.run_once()
    failed = fixture.result(result_id)
    assert failed["draft"]["status"] == "failed"
    assert failed["draft"]["conclusion"] is None
    assert failed["latest_revision_id"] == v2.json()["id"]
    assert failed["latest_version"] == 2
    assert len(table_rows(database, "result_revision", result_id=UUID(result_id))) == 2


@pytest.mark.asyncio
async def test_simultaneous_approvals_conflict_without_overwriting_and_replay_is_safe(summary_fixture, database):
    fixture = summary_fixture
    created = fixture.summary().json()
    result_id, run_id = created["id"], created["draft"]["run_id"]
    await fixture.app.state.container.execution_runtime.worker.run_once()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(fixture.save, result_id, run_id, conclusion=text, client=client)
                   for text, client in (("첫 검토자의 결론", fixture.client), ("다른 검토자의 결론", fixture.editor))]
        responses = [future.result(timeout=10) for future in futures]
    assert sorted(response.status_code for response in responses) == [200, 409]
    loser = next(response for response in responses if response.status_code == 409)
    assert error_code(loser) == "VERSION_CONFLICT"
    revisions = table_rows(database, "result_revision", result_id=UUID(result_id))
    assert len(revisions) == 1
    assert fixture.result(result_id)["latest_version"] == 1


@pytest.mark.parametrize("operation", ["summary", "approval"])
@pytest.mark.asyncio
async def test_receipt_replay_rechecks_project_membership(summary_fixture, database, operation):
    fixture = summary_fixture
    summary_key = new_key()
    created = fixture.summary(headers=summary_key)
    assert created.status_code == 200, created.text
    result_id, run_id = created.json()["id"], created.json()["draft"]["run_id"]

    if operation == "summary":
        original = created

        def replay():
            return fixture.summary(headers=summary_key)
    else:
        await fixture.app.state.container.execution_runtime.worker.run_once()
        save_key = new_key()
        original = fixture.save(result_id, run_id, headers=save_key)
        assert original.status_code == 200, original.text

        def replay():
            return fixture.save(result_id, run_id, headers=save_key)

    assert replay().json() == original.json()
    with database.transaction() as session:
        membership = metadata.tables["membership"]
        session.execute(delete(membership).where(
            membership.c.project_id == fixture.project_id,
            membership.c.account_id == fixture.account_id,
        ))

    rejected = replay()
    assert rejected.status_code == 404, rejected.text
    assert error_code(rejected) == "NOT_FOUND"
    assert fixture.client.get(f"/api/results/{result_id}").status_code == 404


@pytest.mark.asyncio
async def test_long_summary_uses_bounded_calls_with_pinned_sources_and_requesters_connection(summary_fixture, database):
    fixture = summary_fixture
    revision1, revision2 = pin_resource(database, fixture)
    created = fixture.summary().json()
    result_id = created["id"]
    await fixture.app.state.container.execution_runtime.worker.run_once()
    approved = fixture.save(result_id, created["draft"]["run_id"]).json()
    before = len(fixture.gateway.calls)
    for _ in range(3):
        last_seq = add_message(database, fixture, "새 조건을 검토합니다." * 1200)

    updated = fixture.summary(client=fixture.editor).json()
    with database.transaction() as session:
        pin = metadata.tables["conversation_resource"]
        session.execute(update(pin).where(pin.c.conversation_id == fixture.conversation_id).values(revision_id=revision2))
    await fixture.app.state.container.execution_runtime.worker.run_once()
    result = fixture.result(result_id)
    assert result["draft"]["status"] == "ready"
    assert result["latest_revision_id"] == approved["id"]
    calls = fixture.gateway.calls[before:]
    assert len(calls) > 1
    for request in calls:
        assert input_size(request) <= SummaryLimits().input_bytes
        assert request.credential_account_id == fixture.editor_id
        assert request.message_to_seq == last_seq
        assert UUID(approved["id"]) in {item.result_revision_id for item in request.context.results}
        resources = json.loads(request.messages[-1].content)["resources"]
        assert len(resources) == 1
        assert resources[0]["revision_id"] == str(revision1)
        assert resources[0]["instructions"] == "고정 지침 1"
        assert "고정 지침 2" not in request.messages[-1].content
    saved = fixture.save(result_id, updated["draft"]["run_id"], version=1)
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 2


@pytest.mark.asyncio
async def test_summary_source_limit_has_actionable_error_and_preserves_approved_version(summary_fixture, database):
    fixture = summary_fixture
    created = fixture.summary().json()
    result_id = created["id"]
    await fixture.app.state.container.execution_runtime.worker.run_once()
    approved = fixture.save(result_id, created["draft"]["run_id"]).json()
    before = len(fixture.gateway.calls)
    for _ in range(24):
        add_message(database, fixture, "한" * 16_000)

    updated = fixture.summary().json()
    await fixture.app.state.container.execution_runtime.worker.run_once()
    result = fixture.result(result_id)
    assert result["draft"]["status"] == "failed"
    assert result["draft"]["error"]["code"] == "SUMMARY_LIMIT_EXCEEDED"
    assert "처리 한도" in result["draft"]["error"]["message"]
    assert result["latest_revision_id"] == approved["id"] and result["latest_version"] == 1
    assert len(fixture.gateway.calls) == before
    assert fixture.client.get(f"/api/tasks/{fixture.task_id}").json()["status"] == "ready"
    run = table_rows(database, "run", id=UUID(updated["draft"]["run_id"]))[0]
    assert run["status"] == "failed" and run["error_code"] == "SUMMARY_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_old_draft_cannot_be_saved_with_new_drafts_provenance(summary_fixture):
    fixture = summary_fixture
    first = fixture.summary().json()
    result_id, first_run = first["id"], first["draft"]["run_id"]
    await fixture.app.state.container.execution_runtime.worker.run_once()
    second = fixture.summary().json()
    assert second["draft"]["run_id"] != first_run
    await fixture.app.state.container.execution_runtime.worker.run_once()
    stale = fixture.save(result_id, first_run)
    assert stale.status_code == 409 and error_code(stale) == "VERSION_CONFLICT"
    assert fixture.result(result_id)["latest_version"] is None
    saved = fixture.save(result_id, second["draft"]["run_id"])
    assert saved.status_code == 200
    assert saved.json()["source"]["run_id"] == second["draft"]["run_id"]


@pytest.mark.asyncio
async def test_cancelled_summary_is_readable_and_can_be_requested_again(summary_fixture, database):
    fixture = summary_fixture
    first = fixture.summary().json()
    result_id, run_id = first["id"], first["draft"]["run_id"]
    with database.transaction() as session:
        fixture.app.state.container.execution_runtime.control.cancel(session, UUID(run_id), fixture.account_id)
    failed = fixture.result(result_id)
    assert failed["draft"]["status"] == "failed"
    replacement = fixture.summary().json()
    assert replacement["draft"]["run_id"] != run_id
    await fixture.app.state.container.execution_runtime.worker.run_once()
    assert fixture.result(result_id)["draft"]["status"] == "ready"


@pytest.mark.asyncio
async def test_invalid_model_output_fails_draft_without_approving(summary_fixture, database):
    fixture = summary_fixture
    fixture.gateway._summary_json = '{"conclusion":" ","next_steps":"unexpected"}'
    created = fixture.summary().json()
    await fixture.app.state.container.execution_runtime.worker.run_once()
    result = fixture.result(created["id"])
    assert result["draft"]["status"] == "failed"
    assert result["draft"]["error"]["code"] == "LLM_OUTPUT_INVALID"
    assert result["latest_version"] is None
    assert not table_rows(database, "result_revision", result_id=UUID(created["id"]))


def test_summary_requires_ready_task_membership_and_current_actors_connection(summary_fixture, database):
    fixture = summary_fixture
    outsider = fixture.summary(client=fixture.outsider)
    assert outsider.status_code == 404
    with database.transaction() as session:
        task = metadata.tables["task"]
        session.execute(update(task).where(task.c.id == fixture.task_id).values(status="running"))
    response = fixture.summary()
    assert response.status_code == 409 and error_code(response) == "TASK_NOT_READY"
    with database.transaction() as session:
        session.execute(update(task).where(task.c.id == fixture.task_id).values(status="ready"))
        connection = metadata.tables["ai_connection"]
        session.execute(update(connection).where(connection.c.account_id == fixture.editor_id).values(status="invalid"))
    disconnected = fixture.summary(client=fixture.editor)
    assert disconnected.status_code == 409 and error_code(disconnected) == "AI_CONNECTION_REQUIRED"
    assert not table_rows(database, "result", source_task_id=fixture.task_id)
    created = fixture.summary().json()
    assert fixture.outsider.get(f"/api/results/{created['id']}").status_code == 404
    assert fixture.save(created["id"], created["draft"]["run_id"], client=fixture.outsider).status_code == 404
    with TestClient(fixture.app, client=(f"anon-{uuid4().hex}", 50000)) as anonymous:
        assert anonymous.get(f"/api/results/{created['id']}").status_code == 401


def test_task_reads_require_membership_and_keep_result_id_without_changing_status(summary_fixture, database):
    fixture = summary_fixture
    detail_path = f"/api/tasks/{fixture.task_id}"
    before = fixture.client.get(detail_path)
    assert before.status_code == 200, before.text
    original = before.json()
    assert original["result_id"] is None and original["status"] == "ready"
    list_path = f"/api/conversations/{original['source_conversation_id']}/tasks"
    items = fixture.editor.get(list_path)
    assert items.status_code == 200
    assert [item["id"] for item in items.json()["items"]] == [str(fixture.task_id)]
    created = fixture.summary().json()
    after = fixture.client.get(detail_path).json()
    assert after["result_id"] == created["id"] and after["status"] == "ready"
    listed = fixture.editor.get(list_path).json()["items"]
    assert listed[0]["result_id"] == created["id"] and listed[0]["status"] == "ready"
    assert fixture.outsider.get(detail_path).status_code == 404
    assert fixture.outsider.get(list_path).status_code == 404
    assert fixture.client.get(f"/api/tasks/{uuid4()}").status_code == 404
    assert fixture.client.get(f"/api/conversations/{uuid4()}/tasks").status_code == 404
    anonymous = TestClient(fixture.app, client=(f"anonymous-{uuid4().hex}", 50000))
    try:
        assert anonymous.get(detail_path).status_code == 401
        assert anonymous.get(list_path).status_code == 401
    finally:
        anonymous.close()
    assert table_rows(database, "task", id=fixture.task_id)[0]["status"] == "ready"
