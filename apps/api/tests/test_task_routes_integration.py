"""Task HTTP routes use the real queue, authorization, receipts, and committed SSE events.

All data lives in conftest's disposable database; FakeLLM never calls a model provider.
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from executor_harness import GatedLLM
from fastapi import FastAPI
from fastapi.testclient import TestClient
from login_flow import login, new_key, unique_email
from sqlalchemy import delete, insert, update
from work_harness import BRANCH_JSON, rows

from ramus_api.main import create_app
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.execution.fakes.llm import FakeLLM
from ramus_api.modules.execution.infrastructure.branch_tasks import SqlBranchTaskStore
from ramus_api.modules.execution.infrastructure.run_store import SqlRunStore
from ramus_api.modules.execution.infrastructure.task_queries import SqlTaskRepository
from ramus_api.modules.results.infrastructure.task_results import SqlTaskResultQuery
from ramus_api.orm_registry import metadata
from ramus_api.shared.domain.primitives import utc_now

pytestmark = pytest.mark.integration


@dataclass
class TaskRig:
    app: FastAPI
    client: TestClient
    teammate: TestClient
    owner: UUID
    other: UUID
    project: UUID
    parent: UUID
    tasks: list[dict[str, Any]]

    @property
    def runtime(self):
        return self.app.state.container.execution_runtime

    def change(self, task: dict, action: str, headers: dict | None = None, *, client=None):
        return (client or self.client).post(
            f"/api/tasks/{task['id']}/{action}", json={}, headers=headers or new_key()
        )


@pytest.fixture
async def rig(database, integration_settings):
    with database.transaction() as session:
        run = metadata.tables["run"]
        session.execute(update(run).where(run.c.status.in_(("pending", "running"))).values(status="cancelled"))
    mailer = FakeMailer()
    app = create_app(integration_settings, mailer=mailer, llm_gateway=FakeLLM(work_json=BRANCH_JSON))
    # Do not enter lifespan: tests explicitly advance the worker, avoiding background queue races.
    host = uuid4().hex
    client = TestClient(app, client=(f"tasks-owner-{host}", 50000))
    teammate = TestClient(app, client=(f"tasks-member-{host}", 50001))
    try:
        identity = login(client, mailer, unique_email("task-owner")).json()
        other = login(teammate, mailer, unique_email("task-member")).json()
        owner, project = UUID(identity["account"]["id"]), UUID(identity["default_project_id"])
        with database.transaction() as session:
            for actor in (owner, UUID(other["account"]["id"])):
                session.execute(insert(metadata.tables["ai_connection"]).values(
                    account_id=actor, provider="openai", ciphertext="fake-only-not-decrypted",
                    status="connected", verified_at=utc_now(),
                ))
        created = client.post(
            f"/api/projects/{project}/conversations", json={"title": "실제 작업 큐"}, headers=new_key()
        )
        assert created.status_code == 200, created.text
        parent = UUID(created.json()["id"])
        posted = client.post(
            f"/api/conversations/{parent}/messages",
            json={"body": "@AI 가입·혜택·해지를 나눠 조사해줘"}, headers=new_key(),
        )
        assert posted.status_code == 200, posted.text
        runtime = app.state.container.execution_runtime
        assert await runtime.worker.run_once()
        await runtime.relay.flush()
        tasks = rows(database, "task", source_run_id=UUID(posted.json()["run"]["id"]))
        tasks.sort(key=lambda task: task["ordinal"])
        assert len(tasks) == 3
        yield TaskRig(app, client, teammate, owner, UUID(other["account"]["id"]), project, parent, tasks)
    finally:
        client.close()
        teammate.close()
        app.state.container.events.close()
        app.state.container.database.dispose()


async def test_queue_and_detail_preserve_result_links_and_hide_internal_state(rig, database):
    target = rig.tasks[0]
    result_id = uuid4()
    with database.transaction() as session:
        session.execute(insert(metadata.tables["result"]).values(
            id=result_id, project_id=rig.project, source_conversation_id=target["child_conversation_id"],
            source_task_id=target["id"], title="기존 결론",
        ))
        session.execute(update(metadata.tables["task"]).where(metadata.tables["task"].c.id == target["id"]).values(
            error_code="provider-private-code", error_params={"private": "never-returned"},
        ))
    response = rig.client.get(f"/api/conversations/{rig.parent}/tasks")
    assert response.status_code == 200, response.text
    tasks = response.json()["items"]
    assert [task["id"] for task in tasks] == [str(task["id"]) for task in rig.tasks]
    assert tasks[0]["result_id"] == str(result_id)
    assert tasks[0]["error"]["code"] == "LLM_UNAVAILABLE"
    assert "current_run_id" not in tasks[0] and "error_params" not in tasks[0]
    assert "private" not in response.text
    assert rig.teammate.get(f"/api/tasks/{target['id']}").json() == tasks[0]
    assert rig.client.get(f"/api/conversations/{target['child_conversation_id']}/tasks").json() == {"items": []}
    cancelled = rig.change(target, "cancel")
    assert cancelled.status_code == 200 and cancelled.json()["result_id"] == str(result_id)


@pytest.mark.parametrize("action", ["cancel", "retry"])
async def test_task_control_checks_session_membership_and_both_request_owners(rig, database, action):
    target = rig.tasks[0]
    anonymous = TestClient(rig.app)
    try:
        # No valid session: the request cannot read or change another participant's work.
        assert anonymous.get(f"/api/tasks/{target['id']}").status_code == 401
        assert anonymous.get(f"/api/conversations/{rig.parent}/tasks").status_code == 401
        assert rig.change(target, action, client=anonymous).status_code == 401
    finally:
        anonymous.close()
    assert rig.change(target, action, client=rig.teammate).status_code == 403
    # Even the original Task owner cannot operate a follow-up run requested by somebody else.
    with database.transaction() as session:
        run = metadata.tables["run"]
        session.execute(update(run).where(run.c.id == target["current_run_id"]).values(
            requested_by=rig.other, credential_account_id=rig.other,
        ))
    assert rig.change(target, action).status_code == 403
    with database.transaction() as session:
        membership = metadata.tables["membership"]
        session.execute(delete(membership).where(
            membership.c.project_id == rig.project, membership.c.account_id == rig.other,
        ))
    assert rig.teammate.get(f"/api/tasks/{target['id']}").status_code == 404
    assert rig.teammate.get(f"/api/conversations/{rig.parent}/tasks").status_code == 404
    assert rig.change(target, action, client=rig.teammate).status_code == 404
    assert rig.client.get(f"/api/tasks/{uuid4()}").status_code == 404
    assert rig.client.get(f"/api/conversations/{uuid4()}/tasks").status_code == 404


async def _task_events(rig, subscription):
    await rig.runtime.relay.flush()
    events = []
    while (event := await subscription.next(timeout=0.01)) is not None:
        if event.name == "task.updated":
            events.append(event)
    return events


async def test_cancel_and_retry_are_idempotent_with_one_committed_task_event_each(rig, database):
    target = rig.tasks[0]
    subscription = rig.app.state.container.events.subscribe(rig.project)
    cancel_key, retry_key = new_key(), new_key()
    cancelled = rig.change(target, "cancel", cancel_key)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert rig.change(target, "cancel", cancel_key).json() == cancelled.json()
    stored, = rows(database, "run", id=target["current_run_id"])
    assert stored["status"] == "cancelled" and stored["attempt"] == 1
    events = await _task_events(rig, subscription)
    assert len(events) == 1 and events[0].data["task"]["status"] == "cancelled"
    assert rig.change(target, "cancel").status_code == 409
    queued = rig.change(target, "retry", retry_key)
    assert queued.status_code == 200 and queued.json()["status"] == "pending"
    assert rig.change(target, "retry", retry_key).json() == queued.json()
    stored, = rows(database, "run", id=target["current_run_id"])
    assert stored["status"] == "pending" and stored["attempt"] == 2
    assert stored["credential_account_id"] == rig.owner
    assert stored["input_snapshot"] == {
        "message_from_seq": None, "message_to_seq": None,
        "resource_revision_ids": [], "input_result_revision_ids": [],
    }
    events = await _task_events(rig, subscription)
    assert len(events) == 1 and events[0].data["task"]["status"] == "pending"
    assert rig.change(target, "retry").status_code == 409
    # Receipt replay is still subject to current project membership.
    with database.transaction() as session:
        membership = metadata.tables["membership"]
        session.execute(delete(membership).where(
            membership.c.project_id == rig.project, membership.c.account_id == rig.owner,
        ))
    assert rig.change(target, "cancel", cancel_key).status_code == 404
    assert rig.change(target, "retry", retry_key).status_code == 404
    subscription.close()


async def test_retry_requires_current_ai_connection_and_rolls_back_receipt(rig, database):
    target = rig.tasks[0]
    assert rig.change(target, "cancel").status_code == 200
    connection = metadata.tables["ai_connection"]
    saved, = rows(database, "ai_connection", account_id=rig.owner)
    with database.transaction() as session:
        session.execute(delete(connection).where(connection.c.account_id == rig.owner))
    retry_key = new_key()
    rejected = rig.change(target, "retry", retry_key)
    assert rejected.status_code == 409 and rejected.json()["error"]["code"] == "AI_CONNECTION_REQUIRED"
    assert rows(database, "run", id=target["current_run_id"])[0]["attempt"] == 1
    with database.transaction() as session:
        session.execute(insert(connection).values(**saved))
    assert rig.change(target, "retry", retry_key).status_code == 200
    assert rows(database, "run", id=target["current_run_id"])[0]["attempt"] == 2


async def test_control_rejects_finished_work_and_never_cancels_a_summary_run(rig, database):
    for _ in rig.tasks:
        assert await rig.runtime.worker.run_once()
    target = rig.tasks[0]
    assert rig.client.get(f"/api/tasks/{target['id']}").json()["status"] == "ready"
    for action in ("cancel", "retry"):
        assert rig.change(target, action).status_code == 409
    result_id, summary_id = uuid4(), uuid4()
    with database.transaction() as session:
        session.execute(insert(metadata.tables["result"]).values(
            id=result_id, project_id=rig.project, source_conversation_id=target["child_conversation_id"],
            source_task_id=target["id"], title="요약",
        ))
        session.execute(insert(metadata.tables["run"]).values(
            id=summary_id, project_id=rig.project, conversation_id=target["child_conversation_id"],
            task_id=target["id"], purpose="summary", target_id=result_id, status="pending",
            requested_by=rig.owner, credential_account_id=rig.owner, input_snapshot={},
        ))
        # Defensive boundary: even an inconsistent pointer must never control a summary run.
        task = metadata.tables["task"]
        session.execute(update(task).where(task.c.id == target["id"]).values(current_run_id=summary_id))
    for action in ("cancel", "retry"):
        assert rig.change(target, action).status_code == 409
    assert rows(database, "run", id=summary_id)[0]["status"] == "pending"


async def test_stale_task_projection_cannot_lock_a_new_current_run(rig, database):
    target = rig.tasks[0]
    repository = SqlTaskRepository(SqlTaskResultQuery())
    with database.transaction() as session:
        stale = repository.get(session, target["id"])
    assert rig.change(target, "cancel").status_code == 200
    # Simulate a new completed work request replacing the old current pointer.
    replacement = uuid4()
    with database.transaction() as session:
        session.execute(insert(metadata.tables["run"]).values(
            id=replacement, project_id=rig.project, conversation_id=target["child_conversation_id"],
            task_id=target["id"], purpose="work", status="succeeded", requested_by=rig.owner,
            credential_account_id=rig.owner, input_snapshot={},
        ))
        task = metadata.tables["task"]
        session.execute(update(task).where(task.c.id == target["id"]).values(current_run_id=replacement, status="ready"))
    with database.transaction() as session:
        assert not repository.lock_current_work_run(session, stale)
    assert rows(database, "run", id=replacement)[0]["status"] == "succeeded"


async def test_retry_waits_for_a_concurrent_new_ai_request_without_deadlocking(rig, database, monkeypatch):
    target = rig.tasks[0]
    assert rig.change(target, "cancel").status_code == 200
    inserted, release, retrying = threading.Event(), threading.Event(), threading.Event()
    original_project, original_requeue = SqlBranchTaskStore.project, SqlRunStore.requeue

    def gated_project(store, session, state, occurred_at):
        if state.conversation_id == target["child_conversation_id"] and state.id != target["current_run_id"]:
            inserted.set()  # New Run holds the active-run unique-index entry before Task projection.
            assert release.wait(5)
        return original_project(store, session, state, occurred_at)

    def observed_requeue(store, session, run_id, now):
        retrying.set()
        return original_requeue(store, session, run_id, now)

    monkeypatch.setattr(SqlBranchTaskStore, "project", gated_project)
    monkeypatch.setattr(SqlRunStore, "requeue", observed_requeue)
    sibling_client = TestClient(rig.app)
    sibling_client.cookies.update(rig.client.cookies)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            fresh = pool.submit(
                sibling_client.post, f"/api/conversations/{target['child_conversation_id']}/messages",
                json={"body": "@AI 새 보완 요청"}, headers=new_key(),
            )
            assert await asyncio.to_thread(inserted.wait, 5)
            retried = pool.submit(rig.change, target, "retry")
            try:
                assert await asyncio.to_thread(retrying.wait, 5)
            finally:
                release.set()
            posted, response = fresh.result(timeout=10), retried.result(timeout=10)
        assert posted.status_code == 200, posted.text
        assert response.status_code == 409 and response.json()["error"]["code"] == "ACTIVE_RUN_EXISTS"
        task, = rows(database, "task", id=target["id"])
        assert str(task["current_run_id"]) == posted.json()["run"]["id"]
        assert rows(database, "run", id=target["current_run_id"])[0]["attempt"] == 1
    finally:
        release.set()
        sibling_client.close()


async def test_retry_guard_rolls_back_when_a_completed_new_run_replaced_the_pointer(rig, database, monkeypatch):
    target = rig.tasks[0]
    assert rig.change(target, "cancel").status_code == 200
    await rig.runtime.relay.flush()
    subscription = rig.app.state.container.events.subscribe(rig.project)
    replacement = uuid4()
    original_requeue = SqlRunStore.requeue

    def replaced_before_requeue(store, session, run_id, now):
        # Another request fully completes between our initial read and entering the unique index.
        with database.transaction() as concurrent:
            concurrent.execute(insert(metadata.tables["run"]).values(
                id=replacement, project_id=rig.project, conversation_id=target["child_conversation_id"],
                task_id=target["id"], purpose="work", status="succeeded", requested_by=rig.owner,
                credential_account_id=rig.owner, input_snapshot={},
            ))
            task = metadata.tables["task"]
            concurrent.execute(update(task).where(task.c.id == target["id"]).values(
                current_run_id=replacement, status="ready",
            ))
        return original_requeue(store, session, run_id, now)

    monkeypatch.setattr(SqlRunStore, "requeue", replaced_before_requeue)
    retry_key = new_key()
    response = rig.change(target, "retry", retry_key)
    assert response.status_code == 409 and response.json()["error"]["code"] == "RUN_NOT_RETRYABLE"
    old, = rows(database, "run", id=target["current_run_id"])
    assert old["status"] == "cancelled" and old["attempt"] == 1
    current, = rows(database, "task", id=target["id"])
    assert current["current_run_id"] == replacement and current["status"] == "ready"
    receipts = rows(database, "request_receipt", idempotency_key=retry_key["Idempotency-Key"])
    assert receipts == []
    assert await _task_events(rig, subscription) == []
    subscription.close()


async def test_http_cancel_discards_a_late_model_result_from_another_worker(rig, database, integration_settings):
    target = rig.tasks[0]
    for sibling in rig.tasks[1:]:
        assert rig.change(sibling, "cancel").status_code == 200
    gated = GatedLLM()
    elsewhere = create_app(integration_settings, llm_gateway=gated)
    running = asyncio.create_task(elsewhere.state.container.execution_runtime.worker.run_once())
    try:
        await asyncio.wait_for(gated.started.wait(), 5)
        cancelled = rig.change(target, "cancel")
        assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
        gated.release.set()
        assert await asyncio.wait_for(running, 5)
        assert rows(database, "run", id=target["current_run_id"])[0]["status"] == "cancelled"
        assert rig.client.get(f"/api/tasks/{target['id']}").json()["status"] == "cancelled"
        messages = rig.client.get(f"/api/conversations/{target['child_conversation_id']}/messages").json()["items"]
        assert [message["author"]["kind"] for message in messages] == ["system"]
    finally:
        gated.release.set()
        if not running.done():
            running.cancel()
            await asyncio.gather(running, return_exceptions=True)
        elsewhere.state.container.database.dispose()
