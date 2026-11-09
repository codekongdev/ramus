"""Stub routes fail with 501 NOT_IMPLEMENTED; the Idempotency-Key header is checked first.

Implemented endpoints leave the 501 check but keep the Idempotency-Key check.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from contract_endpoints import CONTRACT_ENDPOINTS, Endpoint
from fastapi.testclient import TestClient

from ramus_api.main import create_app
from ramus_api.settings import Settings

KEY = {"Idempotency-Key": "test-key-1"}
ID = str(uuid4())

# P0-A4 login; covered by test_access_*_integration.py.
IMPLEMENTED = frozenset({"requestEmailCode", "verifyEmailCode", "logout", "getMe"})
STUBS = tuple(e for e in CONTRACT_ENDPOINTS if e.operation_id not in IMPLEMENTED)

BODIES: dict[str, dict] = {
    "requestEmailCode": {"email": "a@example.com"},
    "verifyEmailCode": {"email": "a@example.com", "code": "123456"},
    "logout": {},
    "connectAi": {"api_key": "placeholder"},
    "createProject": {"name": "Project"},
    "createConversation": {"title": "Title"},
    "postMessage": {"body": "hello"},
    "cancelTask": {},
    "retryTask": {},
    "createResource": {
        "kind": "text",
        "name": "Name",
        "description": "Description",
        "instructions": None,
        "content": "content",
        "file_name": None,
    },
    "createResourceRevision": {
        "base_revision_id": ID,
        "name": "Name",
        "description": "Description",
        "instructions": None,
        "content": "content",
        "file_name": None,
    },
    "replaceAppliedResources": {"revision_ids": [ID]},
    "createTaskSummary": {},
    "saveResultRevision": {"base_version": 0, "conclusion": "conclusion"},
    "shareResultRevision": {"conversation_ids": [ID]},
    "createConversationFromResult": {"result_revision_id": ID, "title": "Title"},
}


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(Settings(_env_file=None))) as test_client:
        yield test_client


def _url(endpoint: Endpoint) -> str:
    path = endpoint.path
    for name in (
        "project_id",
        "conversation_id",
        "task_id",
        "resource_id",
        "result_id",
        "result_revision_id",
    ):
        path = path.replace("{" + name + "}", ID)
    return path


def _send(client: TestClient, endpoint: Endpoint, headers: dict[str, str]):
    kwargs: dict = {"headers": headers}
    if endpoint.is_change and endpoint.method != "delete":
        kwargs["json"] = BODIES[endpoint.operation_id]
    return client.request(endpoint.method.upper(), _url(endpoint), **kwargs)


def _ids(endpoints) -> list[str]:
    return [e.operation_id for e in endpoints]


@pytest.mark.parametrize("endpoint", STUBS, ids=_ids(STUBS))
def test_every_stub_returns_501_with_a_korean_message(client: TestClient, endpoint: Endpoint) -> None:
    response = _send(client, endpoint, KEY if endpoint.is_change else {})
    assert response.status_code == 501
    error = response.json()["error"]
    assert error["code"] == "NOT_IMPLEMENTED"
    assert error["details"] is None
    assert any("가" <= ch <= "힣" for ch in error["message"])


@pytest.mark.parametrize(
    "endpoint",
    [e for e in CONTRACT_ENDPOINTS if e.is_change],
    ids=_ids([e for e in CONTRACT_ENDPOINTS if e.is_change]),
)
def test_change_routes_check_the_idempotency_key_before_501(client: TestClient, endpoint: Endpoint) -> None:
    response = _send(client, endpoint, {})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_INVALID"


def test_malformed_idempotency_key_is_rejected(client: TestClient) -> None:
    response = client.post("/api/projects", json={"name": "P"}, headers={"Idempotency-Key": "not valid!"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_INVALID"


def test_invalid_body_is_422_invalid_input(client: TestClient) -> None:
    response = client.post("/api/projects", json={}, headers=KEY)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_message_body_longer_than_the_limit_is_rejected(client: TestClient) -> None:
    response = client.post(f"/api/conversations/{ID}/messages", json={"body": "a" * 20_001}, headers=KEY)
    assert response.status_code == 422


def test_message_limit_is_capped_at_200(client: TestClient) -> None:
    response = client.get(f"/api/conversations/{ID}/messages", params={"limit": 201})
    assert response.status_code == 422
    assert client.get(f"/api/conversations/{ID}/messages", params={"limit": 200}).status_code == 501


def test_share_with_no_targets_reaches_the_handler(client: TestClient) -> None:
    # Contract 1.2: an empty target list is SHARE_TARGET_INVALID (business rule), not INVALID_INPUT.
    response = client.post(f"/api/result-revisions/{ID}/shares", json={"conversation_ids": []}, headers=KEY)
    assert response.status_code == 501


def test_share_to_more_than_20_targets_is_rejected(client: TestClient) -> None:
    ids = [str(uuid4()) for _ in range(21)]
    response = client.post(f"/api/result-revisions/{ID}/shares", json={"conversation_ids": ids}, headers=KEY)
    assert response.status_code == 422
