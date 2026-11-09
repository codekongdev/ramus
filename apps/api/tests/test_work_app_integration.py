"""HTTP @AI requests reach the real A5 worker through the application's lifespan."""

import time
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from login_flow import login, new_key, unique_email
from sqlalchemy import update
from work_harness import BRANCH_JSON, rows

from ramus_api.main import create_app
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.access.infrastructure.models import AIConnectionRow
from ramus_api.modules.execution.fakes.llm import FakeLLM
from ramus_api.orm_registry import metadata
from ramus_api.shared.domain.primitives import utc_now

pytestmark = pytest.mark.integration


def test_http_ai_message_branches_and_children_finish_under_application_lifespan(database, integration_settings):
    with database.transaction() as session:
        run = metadata.tables["run"]
        session.execute(update(run).where(run.c.status.in_(("pending", "running"))).values(status="cancelled"))
    gateway, mailer = FakeLLM(work_json=BRANCH_JSON), FakeMailer()
    app = create_app(integration_settings, mailer=mailer, llm_gateway=gateway)
    assert app.state.container.execution_runtime is not None
    with TestClient(app, client=(f"a5-{uuid4().hex}", 50000)) as client:
        identity = login(client, mailer, unique_email("branch-owner")).json()
        account_id, project_id = UUID(identity["account"]["id"]), identity["default_project_id"]
        with app.state.container.database.transaction() as session:
            # FakeLLM never decrypts this fixture value or calls a real model provider.
            session.add(AIConnectionRow(
                account_id=account_id, provider="openai", ciphertext="fixture-only-ciphertext",
                status="connected", verified_at=utc_now(),
            ))
        created = client.post(
            f"/api/projects/{project_id}/conversations", json={"title": "HTTP 멤버십 조사"}, headers=new_key()
        )
        assert created.status_code == 200, created.text
        parent_id = created.json()["id"]
        response = client.post(
            f"/api/conversations/{parent_id}/messages",
            json={"body": "@AI 가입·혜택·해지로 벤치마킹을 나눠 진행해줘"}, headers=new_key(),
        )
        assert response.status_code == 200, response.text
        parent_run_id = UUID(response.json()["run"]["id"])
        continued = client.post(
            f"/api/conversations/{parent_id}/messages", json={"body": "팀 논의를 이어갑니다."}, headers=new_key()
        )
        assert continued.status_code == 200 and continued.json()["run"] is None
        deadline = time.monotonic() + 10
        while True:
            tasks = rows(database, "task", source_run_id=parent_run_id)
            if len(tasks) == 3 and {task["status"] for task in tasks} == {"ready"}:
                break
            assert time.monotonic() < deadline, [(task["title"], task["status"]) for task in tasks]
            time.sleep(0.02)
        conversations = client.get(f"/api/projects/{project_id}/conversations")
        assert conversations.status_code == 200, conversations.text
        children = [item for item in conversations.json()["items"] if item["parent_id"] == parent_id]
        assert len(children) == 3
        assert {child["task_id"] for child in children} == {str(task["id"]) for task in tasks}
        for child in children:
            detail = client.get(f"/api/conversations/{child['id']}")
            assert detail.status_code == 200 and detail.json()["active_run"] is None
            messages = client.get(f"/api/conversations/{child['id']}/messages")
            assert messages.status_code == 200
            assert [message["author"]["kind"] for message in messages.json()["items"]] == ["system", "ai"]
        parent_messages = client.get(f"/api/conversations/{parent_id}/messages").json()["items"]
        assert len([message for message in parent_messages if message["author"]["kind"] == "ai"]) == 1
        assert any(message["body"] == "별도 작업 3개로 나눠 진행합니다." for message in parent_messages)
        assert len(gateway.calls) == 4
        assert {call.credential_account_id for call in gateway.calls} == {account_id}
