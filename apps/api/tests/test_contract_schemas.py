"""Component schemas of docs/contracts.md section 2 are present, snake_case, and use the contract values."""

from __future__ import annotations

import re

import pytest

from ramus_api.main import create_app
from ramus_api.settings import Settings

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")

CONTRACT_SCHEMAS = (
    "Account",
    "Me",
    "Project",
    "Conversation",
    "Message",
    "Run",
    "Task",
    "ResourceSummary",
    "ResourceRevision",
    "ResourceDetail",
    "AppliedResource",
    "ResultDraft",
    "Result",
    "ResultRevision",
    "ConversationInput",
)


@pytest.fixture(scope="module")
def schemas() -> dict[str, dict]:
    return create_app(Settings(_env_file=None)).openapi()["components"]["schemas"]


def _enum(schema: dict) -> list[str]:
    if "enum" in schema:
        return schema["enum"]
    options = [option for option in schema.get("anyOf", []) if option.get("type") != "null"]
    assert len(options) == 1, schema
    return options[0]["enum"]


def _nullable(schema: dict) -> bool:
    return any(option.get("type") == "null" for option in schema.get("anyOf", []))


@pytest.mark.parametrize("name", CONTRACT_SCHEMAS)
def test_contract_schema_exists(schemas: dict, name: str) -> None:
    assert name in schemas


def test_me_has_default_project_id_account_and_ai_connection(schemas: dict) -> None:
    properties = schemas["Me"]["properties"]
    assert {"account", "default_project_id", "ai_connection"} <= set(properties)
    assert _enum(schemas["AiConnectionState"]["properties"]["status"]) == ["none", "connected", "invalid"]


def test_task_status_values(schemas: dict) -> None:
    status = schemas["Task"]["properties"]["status"]
    assert _enum(status) == ["pending", "running", "ready", "failed", "cancelled"]


def test_run_values(schemas: dict) -> None:
    properties = schemas["Run"]["properties"]
    assert _enum(properties["purpose"]) == ["work", "summary"]
    assert _enum(properties["status"]) == ["pending", "running", "succeeded", "failed", "cancelled"]
    assert _nullable(properties["error"])
    assert _nullable(properties["task_id"])


def test_conversation_input_origin(schemas: dict) -> None:
    assert _enum(schemas["ConversationInput"]["properties"]["origin"]) == ["share", "new_conversation"]


def test_share_outcome_values(schemas: dict) -> None:
    outcomes = [
        _enum(schema["properties"]["outcome"])
        for schema in schemas.values()
        if "outcome" in schema.get("properties", {})
    ]
    assert outcomes == [["linked", "replaced", "unchanged", "kept_newer"]]


def test_message_author_kinds(schemas: dict) -> None:
    author = schemas["MessageAuthor"]["properties"]
    assert _enum(author["kind"]) == ["human", "ai", "system"]
    assert _nullable(author["account_id"])


def test_resource_kinds_and_result_draft_status(schemas: dict) -> None:
    assert _enum(schemas["ResourceSummary"]["properties"]["kind"]) == ["skill", "text", "file"]
    assert _enum(schemas["ResultDraft"]["properties"]["status"]) == ["generating", "ready", "failed"]


def test_conversation_fields(schemas: dict) -> None:
    schema = schemas["Conversation"]
    assert set(schema["properties"]) == {
        "id",
        "project_id",
        "parent_id",
        "task_id",
        "title",
        "path",
        "created_by",
        "created_at",
    }
    assert set(schema["required"]) == set(schema["properties"])
    assert _nullable(schema["properties"]["parent_id"])


def test_conversation_detail_adds_active_run(schemas: dict) -> None:
    assert "active_run" in schemas["ConversationDetail"]["properties"]


def test_graph_edge_uses_from_and_to(schemas: dict) -> None:
    assert set(schemas["GraphEdge"]["properties"]) == {"kind", "from", "to"}
    assert _enum(schemas["GraphEdge"]["properties"]["kind"]) == ["branch", "uses_result"]


def test_message_page_has_a_cursor(schemas: dict) -> None:
    assert set(schemas["MessageList"]["properties"]) == {"items", "next_after_seq"}


def test_empty_request_and_response_have_no_fields(schemas: dict) -> None:
    assert schemas["EmptyRequest"].get("properties", {}) == {}
    assert schemas["EmptyResponse"].get("properties", {}) == {}


def test_every_property_name_is_snake_case(schemas: dict) -> None:
    offenders = [
        f"{name}.{prop}"
        for name, schema in schemas.items()
        for prop in schema.get("properties", {})
        if not SNAKE_CASE.match(prop)
    ]
    assert offenders == []


def test_every_list_wrapper_is_an_items_object(schemas: dict) -> None:
    wrappers = {name: s for name, s in schemas.items() if name.endswith("List")}
    assert wrappers
    for name, schema in wrappers.items():
        assert "items" in schema["properties"], name
        assert schema["properties"]["items"]["type"] == "array", name
