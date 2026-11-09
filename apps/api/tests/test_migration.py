from collections.abc import Callable

import pytest
from sqlalchemy import create_engine, inspect

pytestmark = pytest.mark.integration

SCHEMA_TABLES = sorted(
    [
        "alembic_version",
        "request_receipt",
        "project",
        "account",
        "membership",
        "email_code",
        "auth_attempt",
        "session",
        "ai_connection",
        "conversation",
        "message",
        "task",
        "run",
        "resource",
        "resource_revision",
        "conversation_resource",
        "result",
        "result_draft",
        "result_revision",
        "share",
        "conversation_input",
        "seed_marker",
    ]
)

RECEIPT_UNIQUE = "uq_request_receipt_actor_id_scope_idempotency_key"


def table_names(database_url: str) -> list[str]:
    engine = create_engine(database_url)
    try:
        return sorted(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_migrations_upgrade_check_downgrade_and_upgrade_again(
    fresh_database_url: str, run_alembic: Callable[..., object]
) -> None:
    run_alembic(fresh_database_url, "upgrade", "head")
    assert table_names(fresh_database_url) == SCHEMA_TABLES

    run_alembic(fresh_database_url, "check")

    run_alembic(fresh_database_url, "downgrade", "base")
    assert table_names(fresh_database_url) == ["alembic_version"]

    run_alembic(fresh_database_url, "upgrade", "head")
    assert table_names(fresh_database_url) == SCHEMA_TABLES


def test_receipt_table_uses_named_unique_constraint(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        constraints = inspect(engine).get_unique_constraints("request_receipt")
    finally:
        engine.dispose()
    assert [(item["name"], item["column_names"]) for item in constraints] == [
        (RECEIPT_UNIQUE, ["actor_id", "scope", "idempotency_key"])
    ]
