"""HTTP-level tests against an app wired to a real (temporary) PostgreSQL database."""

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ramus_api.container import AppContainer
from ramus_api.main import create_app
from ramus_api.settings import Settings
from ramus_api.shared.domain import BusinessError
from ramus_api.shared.infrastructure.receipts import RequestReceiptRow
from ramus_api.shared.presentation import IdempotencyKey

pytestmark = pytest.mark.integration

SECRET_FAILURE = "database-side-failure-detail"


class CreateItem(BaseModel):
    name: str = Field(min_length=1)


def probe_router(container: AppContainer, calls: list[str]) -> APIRouter:
    router = APIRouter(prefix="/probe")

    @router.post("/items")
    def create_item(data: CreateItem, key: IdempotencyKey) -> dict[str, Any]:
        def operation(session: Session) -> dict[str, Any]:
            calls.append(data.name)
            session.execute(text("SELECT 1"))
            return {"name": data.name, "sequence": len(calls)}

        payload = data.model_dump()
        return container.idempotency.execute_once("probe-actor", "probe.items", key, payload, operation)

    @router.get("/business")
    def business() -> dict[str, str]:
        with container.database.transaction() as session:
            session.execute(text("SELECT 1"))
        raise BusinessError("PROBE_NOT_ALLOWED", "이 작업은 허용되지 않습니다.", 403)

    @router.get("/crash")
    def crash() -> dict[str, str]:
        with container.database.transaction() as session:
            session.execute(text("SELECT 1"))
        raise RuntimeError(SECRET_FAILURE)

    return router


@pytest.fixture
def calls() -> list[str]:
    return []


@pytest.fixture
def app(integration_settings: Settings, calls: list[str]) -> FastAPI:
    instance = create_app(integration_settings)
    instance.include_router(probe_router(instance.state.container, calls))
    return instance


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as instance:
        yield instance


def error_code(response) -> str:
    body = response.json()
    assert set(body["error"]) == {"code", "message", "details"}
    return body["error"]["code"]


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_idempotent_route_replays_and_detects_conflicts(client: TestClient, app: FastAPI,
                                                         calls: list[str]) -> None:
    headers = {"Idempotency-Key": f"item-{uuid4()}"}
    first = client.post("/probe/items", json={"name": "첫 항목"}, headers=headers)
    replay = client.post("/probe/items", json={"name": "첫 항목"}, headers=headers)
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json() == {"name": "첫 항목", "sequence": 1}
    assert calls == ["첫 항목"]

    conflict = client.post("/probe/items", json={"name": "다른 항목"}, headers=headers)
    assert conflict.status_code == 409
    assert error_code(conflict) == "IDEMPOTENCY_CONFLICT"

    with app.state.container.database.transaction() as session:
        keys = session.scalars(select(RequestReceiptRow.idempotency_key).where(
            RequestReceiptRow.idempotency_key == headers["Idempotency-Key"])).all()
    assert keys == [headers["Idempotency-Key"]]


def test_missing_idempotency_key_is_rejected_before_any_side_effect(client: TestClient,
                                                                     calls: list[str]) -> None:
    response = client.post("/probe/items", json={"name": "항목"})
    assert response.status_code == 400
    assert error_code(response) == "IDEMPOTENCY_KEY_INVALID"
    assert calls == []


def test_business_error_envelope(client: TestClient) -> None:
    response = client.get("/probe/business")
    assert response.status_code == 403
    assert error_code(response) == "PROBE_NOT_ALLOWED"
    assert response.json()["error"]["message"] == "이 작업은 허용되지 않습니다."


def test_validation_error_envelope(client: TestClient, calls: list[str]) -> None:
    response = client.post("/probe/items", json={"name": ""}, headers={"Idempotency-Key": "k-1"})
    assert response.status_code == 422
    assert error_code(response) == "INVALID_INPUT"
    assert calls == []


def test_not_found_envelope(client: TestClient) -> None:
    response = client.get("/api/missing")
    assert response.status_code == 404
    assert error_code(response) == "NOT_FOUND"


def test_internal_error_envelope_hides_exception_message(client: TestClient) -> None:
    response = client.get("/probe/crash")
    assert response.status_code == 500
    assert error_code(response) == "INTERNAL_ERROR"
    assert SECRET_FAILURE not in response.text
