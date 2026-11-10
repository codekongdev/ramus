"""Every endpoint of docs/contracts.md section 3 exists in the OpenAPI document, and nothing else does."""

from __future__ import annotations

import pytest
from contract_endpoints import (
    CONTRACT_ENDPOINTS,
    HEALTH_ENDPOINT,
    Endpoint,
    normalise_path,
)

from ramus_api.main import create_app
from ramus_api.settings import Settings

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}
IDEMPOTENCY_HEADER = "Idempotency-Key"


@pytest.fixture(scope="module")
def app():
    return create_app(Settings(_env_file=None))


@pytest.fixture(scope="module")
def document(app) -> dict:
    return app.openapi()


@pytest.fixture(scope="module")
def operations(document: dict) -> dict[tuple[str, str], dict]:
    return {
        (method, normalise_path(path)): operation
        for path, item in document["paths"].items()
        for method, operation in item.items()
        if method in HTTP_METHODS
    }


def _ids(endpoints: tuple[Endpoint, ...]) -> list[str]:
    return [f"{e.method.upper()} {e.path}" for e in endpoints]


def test_contract_table_has_no_duplicates() -> None:
    keys = [endpoint.key for endpoint in CONTRACT_ENDPOINTS]
    assert len(keys) == len(set(keys))
    assert len({endpoint.operation_id for endpoint in CONTRACT_ENDPOINTS}) == len(CONTRACT_ENDPOINTS)


def test_contract_table_has_all_section_3_endpoints() -> None:
    assert len(CONTRACT_ENDPOINTS) == 42


@pytest.mark.parametrize("endpoint", CONTRACT_ENDPOINTS, ids=_ids(CONTRACT_ENDPOINTS))
def test_endpoint_is_in_the_openapi_document(endpoint: Endpoint, operations: dict) -> None:
    assert endpoint.key in operations


def test_nothing_outside_the_contract_is_registered(operations: dict) -> None:
    expected = {endpoint.key for endpoint in CONTRACT_ENDPOINTS} | {
        (HEALTH_ENDPOINT[0], normalise_path(HEALTH_ENDPOINT[1]))
    }
    assert set(operations) == expected


@pytest.mark.parametrize("endpoint", CONTRACT_ENDPOINTS, ids=_ids(CONTRACT_ENDPOINTS))
def test_operation_id_and_tag_follow_the_owning_module(endpoint: Endpoint, operations: dict) -> None:
    operation = operations[endpoint.key]
    assert operation["operationId"] == endpoint.operation_id
    assert operation["tags"] == [endpoint.module]


@pytest.mark.parametrize("endpoint", CONTRACT_ENDPOINTS, ids=_ids(CONTRACT_ENDPOINTS))
def test_change_routes_require_the_idempotency_key_header(endpoint: Endpoint, operations: dict) -> None:
    operation = operations[endpoint.key]
    headers = [p for p in operation.get("parameters", []) if p["in"] == "header"]
    names = {parameter["name"] for parameter in headers}
    assert (IDEMPOTENCY_HEADER in names) is endpoint.is_change


@pytest.mark.parametrize(
    "endpoint", [e for e in CONTRACT_ENDPOINTS if e.status != 200], ids=lambda e: e.operation_id
)
def test_documented_success_status(endpoint: Endpoint, operations: dict) -> None:
    assert str(endpoint.status) in operations[endpoint.key]["responses"]


def test_events_endpoint_documents_server_sent_events(operations: dict) -> None:
    responses = operations[("get", "/api/projects/{}/events")]["responses"]
    assert list(responses["200"]["content"]) == ["text/event-stream"]


def test_error_responses_use_the_error_envelope(document: dict) -> None:
    operation = document["paths"]["/api/projects"]["post"]
    schema = operation["responses"]["4XX"]["content"]["application/json"]["schema"]
    assert schema == {"$ref": "#/components/schemas/ErrorResponse"}
    assert "422" not in operation["responses"]
    assert "HTTPValidationError" not in document["components"]["schemas"]


@pytest.mark.parametrize("endpoint", [e for e in CONTRACT_ENDPOINTS], ids=_ids(CONTRACT_ENDPOINTS))
def test_json_change_routes_with_a_body_declare_json_content(endpoint: Endpoint, operations: dict) -> None:
    body = operations[endpoint.key].get("requestBody")
    if endpoint.is_change and endpoint.method != "delete":
        assert body is not None and body["required"] is True
        assert list(body["content"]) == ["application/json"]
    else:
        assert body is None
