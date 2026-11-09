"""B2 HTTP revisions against a disposable PostgreSQL database; no mail or model calls."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from login_flow import login, new_key, unique_email
from sqlalchemy import delete, func, select

from ramus_api.main import create_app
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.access.infrastructure.models import MembershipRow
from ramus_api.modules.execution.infrastructure.models import RunRow
from ramus_api.modules.projects.infrastructure.models import ProjectRow
from ramus_api.modules.resources.infrastructure.context_provider import build_context_provider
from ramus_api.modules.resources.infrastructure.models import ResourceRevisionRow
from ramus_api.shared.infrastructure.receipts import RequestReceiptRow

pytestmark = pytest.mark.integration


@pytest.fixture
def workspace(integration_settings):
    mailer = FakeMailer()
    app = create_app(integration_settings, mailer=mailer)
    with ExitStack() as stack:
        first = stack.enter_context(TestClient(app, client=(f"b2-{uuid4().hex}", 50000)))
        second = TestClient(app, client=(f"b2-{uuid4().hex}", 50001))
        stack.callback(second.close)
        profiles = [login(client, mailer, unique_email("b2")).json() for client in (first, second)]
        assert profiles[0]["default_project_id"] == profiles[1]["default_project_id"]
        yield app, first, second, profiles


def create_resource(client, project_id, *, kind="skill", **fields):
    content = {"instructions": "지침 v1"} if kind == "skill" else {"content": "자료 v1"}
    if kind == "file":
        content["file_name"] = "criteria-v1.md"
    response = client.post(
        f"/api/projects/{project_id}/resources",
        json={"kind": kind, "name": f"조사 기준 {uuid4().hex}", "description": "첫 기준", **content, **fields},
        headers=new_key("resource"),
    )
    assert response.status_code == 200, response.text
    return response.json()


def revision_body(revision, **changes):
    return {
        "base_revision_id": revision["id"],
        **{field: revision[field] for field in ("name", "description", "instructions", "content", "file_name")},
        **changes,
    }


def save_revision(client, resource_id, body, headers=None):
    return client.post(f"/api/resources/{resource_id}/revisions", json=body, headers=headers or new_key("revision"))


def create_conversation(client, project_id):
    response = client.post(
        f"/api/projects/{project_id}/conversations", json={"title": "버전 검증 대화"}, headers=new_key("conversation")
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def apply_revision(client, conversation_id, revision_id):
    response = client.put(
        f"/api/conversations/{conversation_id}/resources",
        json={"revision_ids": [revision_id]}, headers=new_key("apply"),
    )
    assert response.status_code == 200, response.text
    return response.json()


def revision_count(app, resource_id):
    with app.state.container.database.transaction() as session:
        return session.scalar(select(func.count()).select_from(ResourceRevisionRow).where(
            ResourceRevisionRow.resource_id == UUID(resource_id)))


@pytest.mark.parametrize("kind", ["skill", "text", "file"])
def test_new_revision_retains_original_content_author_and_timestamp(workspace, kind):
    app, first, second, profiles = workspace
    resource = create_resource(first, profiles[0]["default_project_id"], kind=kind)
    original = resource["revision"]
    changes = {"instructions": "지침 v2"} if kind == "skill" else {"content": "자료 v2"}
    if kind == "file":
        changes["file_name"] = "criteria-v2.txt"
    response = save_revision(second, resource["id"], revision_body(original, **changes))
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["created"] is True
    latest = saved["revision"]
    assert latest["number"] == 2
    assert latest["created_by"] == profiles[1]["account"]["id"]
    assert datetime.fromisoformat(latest["created_at"]).tzinfo is not None
    assert original["created_by"] == profiles[0]["account"]["id"]
    assert latest["id"] != original["id"]
    for field, value in changes.items():
        assert latest[field] == value
    detail = first.get(f"/api/resources/{resource['id']}").json()
    assert detail["revision"] == latest
    assert detail["latest_revision_id"] == latest["id"]
    assert [(entry["id"], entry["number"], entry["created_by"]) for entry in detail["revisions"]] == [
        (original["id"], 1, profiles[0]["account"]["id"]),
        (latest["id"], 2, profiles[1]["account"]["id"]),
    ]
    previous = first.get(f"/api/resources/{resource['id']}", params={"revision_id": original["id"]}).json()
    assert previous["revision"] == original
    assert previous["latest_revision_id"] == latest["id"]
    assert first.get(f"/api/resources/{resource['id']}").json() == detail
    assert revision_count(app, resource["id"]) == 2


def test_stale_base_reports_latest_without_overwriting_either_revision(workspace):
    app, first, second, profiles = workspace
    resource = create_resource(first, profiles[0]["default_project_id"])
    original = resource["revision"]
    saved = save_revision(second, resource["id"], revision_body(original, instructions="팀원의 새 지침")).json()
    response = save_revision(first, resource["id"], revision_body(original, instructions="내 편집 초안"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"
    assert response.json()["error"]["details"] == {
        "latest_revision_id": saved["revision"]["id"], "latest_number": 2,
    }
    assert first.get(f"/api/resources/{resource['id']}").json()["revision"] == saved["revision"]
    assert first.get(f"/api/resources/{resource['id']}", params={"revision_id": original["id"]}).json()["revision"] == original
    assert revision_count(app, resource["id"]) == 2


@pytest.mark.parametrize("changes", [
    {"name": " \n"}, {"instructions": " \t"}, {"description": "x" * 2_001},
])
def test_invalid_revision_preserves_latest_and_leaves_no_receipt(workspace, changes):
    app, first, _, profiles = workspace
    resource = create_resource(first, profiles[0]["default_project_id"])
    key = new_key("invalid-revision")
    response = save_revision(first, resource["id"], revision_body(resource["revision"], **changes), key)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"
    assert first.get(f"/api/resources/{resource['id']}").json() == resource
    assert revision_count(app, resource["id"]) == 1
    with app.state.container.database.transaction() as session:
        assert session.scalar(select(RequestReceiptRow.id).where(
            RequestReceiptRow.actor_id == profiles[0]["account"]["id"],
            RequestReceiptRow.idempotency_key == key["Idempotency-Key"],
        )) is None


def test_simultaneous_edits_on_one_base_commit_one_revision_and_one_conflict(workspace):
    app, first, second, profiles = workspace
    resource = create_resource(first, profiles[0]["default_project_id"])
    gate = Barrier(2)

    def submit(index):
        gate.wait(timeout=10)
        return save_revision(
            (first, second)[index], resource["id"],
            revision_body(resource["revision"], instructions=f"동시 수정 {index}"),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(submit, index) for index in range(2)]
        responses = [future.result(timeout=15) for future in futures]
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(index for index, response in enumerate(responses) if response.status_code == 200)
    latest = responses[winner].json()["revision"]
    conflict = responses[1 - winner].json()["error"]
    assert (latest["number"], latest["instructions"], latest["created_by"]) == (
        2, f"동시 수정 {winner}", profiles[winner]["account"]["id"],
    )
    assert conflict["code"] == "VERSION_CONFLICT"
    assert conflict["details"] == {"latest_revision_id": latest["id"], "latest_number": 2}
    assert revision_count(app, resource["id"]) == 2


def test_concurrent_replay_and_unchanged_save_do_not_duplicate_revisions(workspace):
    app, first, _, profiles = workspace
    resource = create_resource(first, profiles[0]["default_project_id"])
    key = new_key("retry")
    body = revision_body(resource["revision"], instructions="한 번만 저장")
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(save_revision, first, resource["id"], body, key) for _ in range(4)]
        responses = [future.result(timeout=15) for future in futures]
    assert [response.status_code for response in responses] == [200] * 4
    assert all(response.json() == responses[0].json() for response in responses)
    revision = responses[0].json()["revision"]
    unchanged = save_revision(first, resource["id"], revision_body(revision))
    assert unchanged.status_code == 200
    assert unchanged.json() == {"revision": revision, "created": False}
    conflict = save_revision(first, resource["id"], {**body, "instructions": "다른 내용"}, key)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    newer = save_revision(first, resource["id"], revision_body(revision, instructions="세 번째 지침"))
    assert newer.status_code == 200
    # A response lost before v3 still replays exactly v2, without a stale-base conflict or another write.
    assert save_revision(first, resource["id"], body, key).json() == responses[0].json()
    assert revision_count(app, resource["id"]) == 3
    with app.state.container.database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(RequestReceiptRow).where(
            RequestReceiptRow.actor_id == profiles[0]["account"]["id"],
            RequestReceiptRow.idempotency_key == key["Idempotency-Key"],
        )) == 1


def test_saving_v2_does_not_change_pins_inherited_pins_or_running_snapshot(workspace):
    app, first, second, profiles = workspace
    project_id = profiles[0]["default_project_id"]
    parent = create_conversation(first, project_id)
    child = create_conversation(first, project_id)
    resource = create_resource(first, project_id)
    original = resource["revision"]
    applied_v1 = apply_revision(first, parent, original["id"])
    provider = build_context_provider()
    run_id = uuid4()
    input_snapshot = {
        "resource_revision_ids": [original["id"]], "input_result_revision_ids": [],
        "message_from_seq": None, "message_to_seq": None,
    }
    with app.state.container.database.transaction() as session:
        provider.copy_resources(session, UUID(parent), UUID(child))
        before = provider.snapshot(session, UUID(parent))
        session.add(RunRow(
            id=run_id, project_id=UUID(project_id), conversation_id=UUID(parent),
            purpose="work", status="running", requested_by=UUID(profiles[0]["account"]["id"]),
            credential_account_id=UUID(profiles[0]["account"]["id"]), input_snapshot=input_snapshot,
        ))
    response = save_revision(second, resource["id"], revision_body(original, instructions="새 실행에 쓸 v2"))
    assert response.status_code == 200
    latest = response.json()["revision"]
    for conversation in (parent, child):
        assert first.get(f"/api/conversations/{conversation}/resources").json() == applied_v1
    with app.state.container.database.transaction() as session:
        assert provider.snapshot(session, UUID(parent)) == before
        assert provider.snapshot(session, UUID(child)) == before
        assert session.get(RunRow, run_id).input_snapshot == input_snapshot
    search = second.get(f"/api/projects/{project_id}/resources", params={"conversation_id": parent}).json()
    hit = next(item for item in search["items"] if item["id"] == resource["id"])
    assert hit["applied"] == {"revision_id": original["id"], "number": 1}
    assert hit["latest"]["revision_id"] == latest["id"]
    apply_revision(first, parent, latest["id"])
    with app.state.container.database.transaction() as session:
        assert provider.snapshot(session, UUID(parent)).resources[0].revision_id == UUID(latest["id"])
        assert provider.snapshot(session, UUID(child)) == before
        assert session.get(RunRow, run_id).input_snapshot == input_snapshot
    # Explicitly selecting an older revision changes the pin, never the project's latest.
    apply_revision(first, parent, original["id"])
    assert first.get(f"/api/resources/{resource['id']}").json()["latest_revision_id"] == latest["id"]


def test_unknown_foreign_revisions_and_nonmembers_do_not_expose_or_change_resources(workspace):
    app, first, second, profiles = workspace
    private_id = uuid4()
    with app.state.container.database.transaction() as session:
        session.add(ProjectRow(id=private_id, name="비공개 버전 검증", is_shared_sample=False))
        session.flush()
        session.add(MembershipRow(project_id=private_id, account_id=UUID(profiles[0]["account"]["id"]), role="editor"))
    resource = create_resource(first, private_id)
    foreign = create_resource(first, private_id)
    for revision_id in (str(uuid4()), foreign["revision"]["id"]):
        response = first.get(f"/api/resources/{resource['id']}", params={"revision_id": revision_id})
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
    hidden = second.get(f"/api/resources/{resource['id']}")
    missing = second.get(f"/api/resources/{uuid4()}")
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()
    rejected = save_revision(second, resource["id"], revision_body(resource["revision"], instructions="접근 불가"))
    assert rejected.status_code == 404
    assert rejected.json()["error"]["code"] == "NOT_FOUND"
    assert revision_count(app, resource["id"]) == 1


def test_resource_changes_recheck_membership_before_replaying_receipts(workspace):
    app, first, _, profiles = workspace
    project_id = profiles[0]["default_project_id"]
    creation_key = new_key("revoke-create")
    creation_body = {"kind": "skill", "name": "접근 회수 검증", "description": "", "instructions": "초기 지침"}
    created = first.post(f"/api/projects/{project_id}/resources", json=creation_body, headers=creation_key)
    assert created.status_code == 200
    resource = created.json()
    key = new_key("revoke-revision")
    body = revision_body(resource["revision"], instructions="회수 전 저장")
    assert save_revision(first, resource["id"], body, key).status_code == 200
    conversation = create_conversation(first, project_id)
    apply_key = new_key("revoke-apply")
    apply_body = {"revision_ids": [resource["revision"]["id"]]}
    assert first.put(f"/api/conversations/{conversation}/resources", json=apply_body, headers=apply_key).status_code == 200
    with app.state.container.database.transaction() as session:
        session.execute(delete(MembershipRow).where(
            MembershipRow.project_id == UUID(project_id),
            MembershipRow.account_id == UUID(profiles[0]["account"]["id"]),
        ))
    assert first.get(f"/api/resources/{resource['id']}").status_code == 404
    replays = [
        first.post(f"/api/projects/{project_id}/resources", json=creation_body, headers=creation_key),
        save_revision(first, resource["id"], body, key),
        first.put(f"/api/conversations/{conversation}/resources", json=apply_body, headers=apply_key),
    ]
    for response in replays:
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
    assert revision_count(app, resource["id"]) == 2
