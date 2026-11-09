"""ON-AC-11: independently authenticated users see one prepared workspace and keep real work."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient
from login_flow import ME_PATH, login, new_key, unique_email
from test_seed import snapshot

from ramus_api.main import create_app
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.projects.public import FOLLOWUP_SAMPLE_PROJECT_ID, SHARED_SAMPLE_PROJECT_ID
from ramus_api.modules.resources.infrastructure.context_provider import build_context_provider
from ramus_api.modules.seed.domain.content import RESEARCH, RESOURCES, sample_id
from ramus_api.modules.seed.infrastructure.sample import prepare_shared_sample
from ramus_api.settings import Settings
from ramus_api.shared.infrastructure.database import Database

pytestmark = pytest.mark.integration


def test_concurrent_first_logins_and_refresh_preserve_one_prepared_sample(fresh_database_url, run_alembic):
    run_alembic(fresh_database_url, "upgrade", "head")
    database = Database(fresh_database_url)
    try:
        prepare_shared_sample(database)
        mailer = FakeMailer()
        app = create_app(Settings(_env_file=None, database_url=fresh_database_url), mailer=mailer)
        design_id = sample_id("conversation:design")
        tree_url = f"/api/projects/{SHARED_SAMPLE_PROJECT_ID}/conversations"
        message_url = f"/api/conversations/{design_id}/messages"
        with ExitStack() as stack:
            clients = [stack.enter_context(TestClient(app)) for _ in range(3)]
            emails = [unique_email(f"seed-{index}") for index in range(3)]
            with ThreadPoolExecutor(max_workers=3) as pool:
                sessions = list(pool.map(lambda pair: login(pair[0], mailer, pair[1]).json(), zip(clients, emails, strict=True)))
            assert {item["default_project_id"] for item in sessions} == {str(SHARED_SAMPLE_PROJECT_ID)}
            trees = [client.get(tree_url).json()["items"] for client in clients]
            assert trees[0] == trees[1] == trees[2]
            assert trees[0][0]["id"] == str(design_id)
            assert len(trees[0]) == 4
            examples = clients[0].get(message_url).json()["items"]
            assert len(examples) == 1
            assert examples[0]["is_example"] is True
            assert examples[0]["author"]["display_name"] == "예시·팀장"
            for client in clients:
                projects = client.get("/api/projects").json()["items"]
                assert {p["id"] for p in projects} == {str(SHARED_SAMPLE_PROJECT_ID), str(FOLLOWUP_SAMPLE_PROJECT_ID)}
                pins = client.get(f"/api/conversations/{design_id}/resources").json()["items"]
                assert {p["revision_id"] for p in pins} == {str(sample_id(f"resource:{r.key}:v1")) for r in RESOURCES}
                for research in RESEARCH:
                    result_id = sample_id(f"result:{research.key}")
                    revision_id = sample_id(f"result:{research.key}:v1")
                    result = client.get(f"/api/results/{result_id}")
                    assert result.status_code == 200, result.text
                    assert result.json()["latest_revision_id"] == str(revision_id)
                    revision = client.get(f"/api/result-revisions/{revision_id}")
                    assert revision.status_code == 200, revision.text
                    assert revision.json()["conclusion"] == research.conclusion
                    assert revision.json()["saved_by"] == str(sample_id(f"author:{research.author_key}"))
            posted = clients[0].post(message_url, json={"body": "팀에서 추가한 실제 정책 논의"}, headers=new_key())
            assert posted.status_code == 200, posted.text
            actual = posted.json()["message"]
            assert actual["is_example"] is False
            assert actual["author"]["account_id"] == sessions[0]["account"]["id"]
            # Refresh, normal preparation and a returning session must preserve the shared discussion.
            before = snapshot(database.engine)
            prepare_shared_sample(database)
            assert snapshot(database.engine) == before
            for client in clients:
                assert client.get(ME_PATH).status_code == 200
                assert client.get(tree_url).json()["items"] == trees[0]
                assert client.get(message_url).json()["items"][-1] == actual
        with database.transaction() as session:
            context = build_context_provider().snapshot(session, design_id)
            assert len(context.resources) == 3
            assert {r.result_revision_id for r in context.results} == {sample_id(f"result:{r.key}:v1") for r in RESEARCH}
            assert all(r.version == 1 and "가상" in r.conclusion for r in context.results)
    finally:
        database.dispose()
