"""Error envelope tests that run without a database (the app never connects at creation time)."""

import logging
from collections.abc import Iterator

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from ramus_api.main import create_app
from ramus_api.settings import Settings
from ramus_api.shared.domain import BusinessError
from ramus_api.shared.presentation import IdempotencyKey

SECRET_INPUT = "sk-submitted-secret-value"
SECRET_FAILURE = "internal-failure-detail-should-not-leak"
ERROR_REF = "#/components/schemas/ErrorResponse"


class ProbeInput(BaseModel):
    name: str = Field(min_length=1)
    count: int


def probe_router() -> APIRouter:
    router = APIRouter(prefix="/probe")

    @router.get("/business")
    def business() -> dict[str, str]:
        raise BusinessError("PROBE_FAILED", "검사용 업무 오류입니다.", 409, {"field": "name"})

    @router.post("/validate")
    def validate(data: ProbeInput) -> ProbeInput:
        return data

    @router.get("/crash")
    def crash() -> dict[str, str]:
        raise RuntimeError(SECRET_FAILURE)

    @router.get("/teapot")
    def teapot() -> dict[str, str]:
        raise HTTPException(status_code=418, detail="english detail", headers={"X-Probe": "1"})

    @router.post("/idempotent")
    def idempotent(key: IdempotencyKey) -> dict[str, str]:
        return {"key": key}

    return router


@pytest.fixture
def app(unit_settings: Settings) -> FastAPI:
    instance = create_app(unit_settings)
    instance.include_router(probe_router())
    return instance


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as instance:
        yield instance


def assert_envelope(body: dict, code: str) -> dict:
    assert set(body) == {"error"}
    error = body["error"]
    assert set(error) == {"code", "message", "details"}
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]
    return error


def test_business_error_keeps_its_status_code_and_details(client: TestClient) -> None:
    response = client.get("/probe/business")
    assert response.status_code == 409
    error = assert_envelope(response.json(), "PROBE_FAILED")
    assert error["message"] == "검사용 업무 오류입니다."
    assert error["details"] == {"field": "name"}


def test_validation_error_lists_locations_without_echoing_input(client: TestClient) -> None:
    response = client.post("/probe/validate", json={"name": "", "count": SECRET_INPUT})
    assert response.status_code == 422
    error = assert_envelope(response.json(), "INVALID_INPUT")
    assert SECRET_INPUT not in response.text
    locations = sorted(tuple(item["location"]) for item in error["details"])
    assert locations == [("body", "count"), ("body", "name")]
    for item in error["details"]:
        assert set(item) == {"location", "type", "message"}


def test_unknown_route_returns_not_found_envelope(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    error = assert_envelope(response.json(), "NOT_FOUND")
    assert error["details"] is None


def test_wrong_method_returns_method_not_allowed_envelope(client: TestClient) -> None:
    response = client.delete("/api/health")
    assert response.status_code == 405
    assert_envelope(response.json(), "METHOD_NOT_ALLOWED")
    assert "GET" in response.headers["allow"]


def test_unmapped_http_exception_keeps_status_and_headers_but_not_detail(client: TestClient) -> None:
    response = client.get("/probe/teapot")
    assert response.status_code == 418
    assert response.headers["x-probe"] == "1"
    assert_envelope(response.json(), "HTTP_418")
    assert "english detail" not in response.text


def test_unhandled_exception_is_logged_but_not_exposed(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        response = client.get("/probe/crash")
    assert response.status_code == 500
    assert_envelope(response.json(), "INTERNAL_ERROR")
    assert SECRET_FAILURE not in response.text
    assert any(record.exc_info and SECRET_FAILURE in str(record.exc_info[1]) for record in caplog.records)


@pytest.mark.parametrize("headers", [{}, {"Idempotency-Key": ""}, {"Idempotency-Key": "bad key"},
                                     {"Idempotency-Key": "x" * 129}])
def test_idempotency_key_header_is_required_and_validated(client: TestClient, headers: dict) -> None:
    response = client.post("/probe/idempotent", headers=headers)
    assert response.status_code == 400
    assert_envelope(response.json(), "IDEMPOTENCY_KEY_INVALID")


def test_valid_idempotency_key_reaches_route(client: TestClient) -> None:
    response = client.post("/probe/idempotent", headers={"Idempotency-Key": "req-1:a.b_c"})
    assert response.status_code == 200
    assert response.json() == {"key": "req-1:a.b_c"}


def test_openapi_error_responses_reference_error_response_schema(app: FastAPI) -> None:
    document = app.openapi()
    schemas = document["components"]["schemas"]
    assert "ErrorResponse" in schemas
    assert "HTTPValidationError" not in schemas
    assert sorted(schemas["ErrorBody"]["required"]) == ["code", "details", "message"]
    for path in ("/api/health", "/probe/validate"):
        operation = next(iter(document["paths"][path].values()))
        for status in ("4XX", "5XX"):
            schema = operation["responses"][status]["content"]["application/json"]["schema"]
            assert schema == {"$ref": ERROR_REF}
    parameters = document["paths"]["/probe/idempotent"]["post"]["parameters"]
    assert any(item["name"] == "Idempotency-Key" and item["in"] == "header" for item in parameters)
