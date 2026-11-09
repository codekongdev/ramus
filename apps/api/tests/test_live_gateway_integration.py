"""Real credential storage, default app assembly and worker; mock only the provider HTTP boundary."""

import json
import secrets
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from login_flow import login, logout, new_key, unique_email
from pydantic import SecretStr
from sqlalchemy import select

from ramus_api import main
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.execution.infrastructure.models import RunRow
from ramus_api.modules.execution.infrastructure.summary_gateway import OpenAiGateway
from ramus_api.modules.seed.domain.content import RESEARCH, RESOURCES, sample_id
from ramus_api.modules.seed.infrastructure.sample import prepare_shared_sample
from ramus_api.settings import Settings
from ramus_api.shared.infrastructure.database import Database

pytestmark = pytest.mark.integration


class TestKeyValidator:
    async def validate(self, api_key: str) -> None:
        pass


def test_default_gateway_uses_each_accounts_key_and_pinned_resource_versions(
    integration_settings, monkeypatch, caplog, no_implicit_model_worker,
):
    calls: list[tuple[str, dict]] = []

    def provider(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append((request.headers["Authorization"], payload))
        return httpx.Response(200, json={
            "status": "completed",
            "error": None,
            "output": [{
                "type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": json.dumps({
                    "mode": "answer", "reply": "고정한 자료를 사용한 응답입니다.", "tasks": [],
                }, ensure_ascii=False)}],
            }],
        })

    def gateway(model, credentials):
        return OpenAiGateway(model, credentials, client_factory=lambda **kwargs: httpx.AsyncClient(
            transport=httpx.MockTransport(provider), **kwargs,
        ))

    monkeypatch.setattr(main, "OpenAiGateway", gateway)
    monkeypatch.setattr(main, "default_gateway", no_implicit_model_worker)
    settings = integration_settings.model_copy(update={"secret_key": SecretStr(secrets.token_urlsafe(32))})
    mailer = FakeMailer()
    app = main.create_app(settings, mailer=mailer, ai_key_validator=TestKeyValidator())
    assert app.state.container.execution_runtime is not None
    synthetic_keys = ["valid-test-live-first", "valid-test-live-second"]
    with TestClient(app, client=(f"live-{secrets.token_hex(6)}", 50000)) as client:
        first = login(client, mailer, unique_email("live-first")).json()
        project_id = first["default_project_id"]
        created = client.post(f"/api/projects/{project_id}/conversations", json={"title": "고정 자료와 계정 키"}, headers=new_key())
        assert created.status_code == 200, created.text
        conversation_id = created.json()["id"]
        resource = client.post(f"/api/projects/{project_id}/resources", json={
            "kind": "skill", "name": "업무 기준", "description": "고정 버전 검증", "instructions": "v1 지침만 사용하세요.",
        }, headers=new_key())
        assert resource.status_code == 200, resource.text
        resource_id = resource.json()["id"]
        revision_id = resource.json()["revision"]["id"]
        applied = client.put(f"/api/conversations/{conversation_id}/resources", json={"revision_ids": [revision_id]}, headers=new_key())
        assert applied.status_code == 200, applied.text
        accounts = [first["account"]["id"]]
        run_ids = []
        for index, key in enumerate(synthetic_keys):
            if index:
                assert logout(client).status_code == 200
                second = login(client, mailer, unique_email("live-second")).json()
                accounts.append(second["account"]["id"])
                revised = client.post(f"/api/resources/{resource_id}/revisions", json={
                    "base_revision_id": revision_id, "name": "업무 기준", "description": "새 버전",
                    "instructions": "v2 지침은 아직 적용하지 않았습니다.",
                }, headers=new_key())
                assert revised.status_code == 200, revised.text
            connected = client.put("/api/me/ai-connection", json={"api_key": key}, headers=new_key())
            assert connected.status_code == 200, connected.text
            response = client.post(f"/api/conversations/{conversation_id}/messages", json={"body": "@AI 적용한 지침으로 답해 주세요."}, headers=new_key())
            assert response.status_code == 200, response.text
            run_ids.append(response.json()["run"]["id"])
            deadline = time.monotonic() + 10
            while True:
                messages = client.get(f"/api/conversations/{conversation_id}/messages").json()["items"]
                completed = [message for message in messages if message["author"]["kind"] == "ai"]
                if len(completed) == index + 1:
                    break
                assert time.monotonic() < deadline, "The default gateway's worker did not finish"
                time.sleep(0.01)
            assert key not in json.dumps(messages, ensure_ascii=False)
        with app.state.container.database.transaction() as session:
            runs = {str(row.id): row for row in session.scalars(select(RunRow).where(RunRow.id.in_(run_ids)))}
            for run_id, account_id in zip(run_ids, accounts, strict=True):
                run = runs[run_id]
                assert run.status == "succeeded"
                assert str(run.credential_account_id) == account_id
                assert run.input_snapshot["resource_revision_ids"] == [revision_id]
        own_calls = [(auth, body) for auth, body in calls if auth in {f"Bearer {key}" for key in synthetic_keys}]
        assert [auth for auth, _ in own_calls] == [f"Bearer {key}" for key in synthetic_keys]
        for _, body in own_calls:
            assert body["store"] is False
            assert body["model"] == settings.openai_model
            assert body["text"]["format"]["strict"] is True
            context = body["input"][1]["content"]
            assert revision_id in context and "v1 지침만 사용하세요." in context
            assert "v2 지침은 아직 적용하지 않았습니다." not in context
    assert all(key not in caplog.text for key in synthetic_keys)


async def test_shared_and_followup_inputs_reach_provider_at_their_pinned_versions(
    fresh_database_url, run_alembic, monkeypatch, no_implicit_model_worker,
):
    run_alembic(fresh_database_url, "upgrade", "head")
    database = Database(fresh_database_url)
    calls = []

    def provider(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={
            "status": "completed", "output": [{
                "type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": json.dumps({
                    "mode": "answer", "reply": "고정 결론으로 검토했습니다.", "tasks": [],
                }, ensure_ascii=False)}],
            }],
        })

    def gateway(model, credentials):
        return OpenAiGateway(model, credentials, client_factory=lambda **options: httpx.AsyncClient(
            transport=httpx.MockTransport(provider), **options,
        ))

    monkeypatch.setattr(main, "OpenAiGateway", gateway)
    monkeypatch.setattr(main, "default_gateway", no_implicit_model_worker)
    app = None
    client = None
    try:
        prepare_shared_sample(database)
        settings = Settings(_env_file=None, database_url=fresh_database_url).model_copy(update={
            "secret_key": SecretStr(secrets.token_urlsafe(32)),
        })
        mailer = FakeMailer()
        app = main.create_app(settings, mailer=mailer, ai_key_validator=TestKeyValidator())
        client = TestClient(app, client=(f"pinned-input-{secrets.token_hex(6)}", 50000))
        identity = login(client, mailer, unique_email("pinned-input")).json()
        project_id = identity["default_project_id"]
        connected = client.put("/api/me/ai-connection", json={"api_key": "valid-test-pinned-input"}, headers=new_key())
        assert connected.status_code == 200, connected.text
        revision_id = str(sample_id(f"result:{RESEARCH[0].key}:v1"))
        revision = client.get(f"/api/result-revisions/{revision_id}").json()
        resource_id = str(sample_id(f"resource:{RESOURCES[0].key}"))
        resource_revision_id = str(sample_id(f"resource:{RESOURCES[0].key}:v1"))

        target = client.post(f"/api/projects/{project_id}/conversations", json={"title": "공유 결론 검토"}, headers=new_key())
        assert target.status_code == 200, target.text
        target_id = target.json()["id"]
        shared = client.post(f"/api/result-revisions/{revision_id}/shares", json={"conversation_ids": [target_id]}, headers=new_key())
        assert shared.status_code == 200, shared.text

        # A source update must not silently replace the conclusion or applied resource.
        updated = client.post(f"/api/results/{revision['result_id']}/revisions", json={
            "base_version": 1, "conclusion": "후속 입력에 자동 적용하면 안 되는 새 결론",
            "source_run_id": revision["source"]["run_id"],
        }, headers=new_key())
        assert updated.status_code == 200, updated.text
        updated_resource = client.post(f"/api/resources/{resource_id}/revisions", json={
            "base_revision_id": resource_revision_id, "name": RESOURCES[0].name, "description": "새 버전",
            "instructions": "후속 입력에 자동 적용하면 안 되는 새 지침",
        }, headers=new_key())
        assert updated_resource.status_code == 200, updated_resource.text
        followup = client.post(f"/api/projects/{project_id}/conversations/from-result", json={
            "result_revision_id": revision_id, "title": "구버전 결론의 후속 대화",
        }, headers=new_key())
        assert followup.status_code == 200, followup.text

        for conversation_id in (target_id, followup.json()["id"]):
            applied = client.put(f"/api/conversations/{conversation_id}/resources",
                                 json={"revision_ids": [resource_revision_id]}, headers=new_key())
            assert applied.status_code == 200, applied.text
            posted = client.post(f"/api/conversations/{conversation_id}/messages",
                                 json={"body": "@AI 연결된 결론과 자료로 검토해 주세요."}, headers=new_key())
            assert posted.status_code == 200, posted.text
            assert await app.state.container.execution_runtime.worker.run_once()
            with database.transaction() as session:
                run = session.get(RunRow, posted.json()["run"]["id"])
                assert run.status == "succeeded"
                assert run.input_snapshot["resource_revision_ids"] == [resource_revision_id]
                assert run.input_snapshot["input_result_revision_ids"] == [revision_id]
                assert str(run.credential_account_id) == identity["account"]["id"]
        assert len(calls) == 2
        for payload in calls:
            context = json.loads(payload["input"][1]["content"].split("\n", 1)[1])
            assert context["results"][0]["result_revision_id"] == revision_id
            assert context["results"][0]["conclusion"] == RESEARCH[0].conclusion
            assert context["resources"][0]["revision_id"] == resource_revision_id
            assert context["resources"][0]["instructions"] == RESOURCES[0].body
            assert "자동 적용하면 안 되는" not in json.dumps(payload, ensure_ascii=False)
    finally:
        if client is not None:
            client.close()
        if app is not None:
            app.state.container.events.close()
            app.state.container.database.dispose()
        database.dispose()
