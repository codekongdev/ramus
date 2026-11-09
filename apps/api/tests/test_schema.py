"""PostgreSQL constraints are tested against migrated temporary databases, never create_all()."""

import re
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, insert, inspect, select, update
from sqlalchemy.exc import IntegrityError

from ramus_api.orm_registry import metadata
from ramus_api.shared.infrastructure.database import Database

pytestmark = pytest.mark.integration


def test_migrated_columns_match_contract_and_all_tables_have_created_at(database_url: str) -> None:
    document = (Path(__file__).resolve().parents[3] / "docs/contracts.md").read_text()
    section = document.split("## 5. 테이블 스키마", 1)[1].split("## 6.", 1)[0]
    expected = {}
    for line in section.splitlines():
        if not line.startswith("| `"):
            continue
        cells = line.split(" | ")
        table = re.search(r"`([a-z_]+)`", cells[0]).group(1)
        columns = re.findall(r"(?:^|,)\s*`([a-z_]+)(?: \\?\| null)?`", cells[2])
        expected[table] = set(columns) | {"created_at"}
    assert len(expected) == 19
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        for table, columns in expected.items():
            actual = inspector.get_columns(table)
            assert {column["name"] for column in actual} == columns, table
            assert all(column["type"].timezone for column in actual if column["name"].endswith("_at"))
    finally:
        engine.dispose()


def test_cyclic_foreign_keys_exist_in_the_database(database_url: str) -> None:
    expected = {
        "conversation": {"fk_conversation_task_id_task"},
        "message": {"fk_message_run_id_run"},
        "task": {"fk_task_current_run_id_run", "fk_task_source_run_id_run"},
        "run": {"fk_run_target_id_result"},
        "resource": {"fk_resource_latest_revision"},
        "result": {"fk_result_latest_revision"},
    }
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        for table, names in expected.items():
            assert names <= {fk["name"] for fk in inspector.get_foreign_keys(table)}
    finally:
        engine.dispose()


def run_values(ids: dict[str, UUID], **overrides) -> dict:
    return {
        "id": uuid4(),
        "project_id": ids["project"],
        "conversation_id": ids["source"],
        "purpose": "work",
        "status": "pending",
        "requested_by": ids["account"],
        "credential_account_id": ids["account"],
        "input_snapshot": {
            "message_from_seq": 1,
            "message_to_seq": 2,
            "resource_revision_ids": [],
            "input_result_revision_ids": [],
        },
        **overrides,
    }


def revision_values(ids: dict[str, UUID], **overrides) -> dict:
    return {
        "id": uuid4(),
        "result_id": ids["result"],
        "version": 1,
        "title": "검토 결과",
        "conclusion": "검토한 결론",
        "source": {},
        "saved_by": ids["account"],
        **overrides,
    }


@pytest.fixture
def records(database: Database) -> Iterator[dict[str, UUID]]:
    ids = {
        name: uuid4()
        for name in [
            "account",
            "project",
            "source",
            "child",
            "target",
            "root_run",
            "task",
            "result",
            "result_revision",
            "resource",
            "resource_revision",
        ]
    }
    with database.transaction() as session:
        session.execute(
            insert(metadata.tables["account"]).values(
                id=ids["account"], email=f"{ids['account']}@example.test", display_name="테스트 참여자"
            )
        )
        session.execute(insert(metadata.tables["project"]).values(id=ids["project"], name="테스트 프로젝트"))
        for name in ["source", "child", "target"]:
            session.execute(
                insert(metadata.tables["conversation"]).values(
                    id=ids[name],
                    project_id=ids["project"],
                    title=name,
                    origin="top",
                    created_by=ids["account"],
                )
            )
        session.execute(
            insert(metadata.tables["run"]).values(**run_values(ids, id=ids["root_run"], status="succeeded"))
        )
        session.execute(
            insert(metadata.tables["task"]).values(
                id=ids["task"],
                source_conversation_id=ids["source"],
                child_conversation_id=ids["child"],
                source_run_id=ids["root_run"],
                ordinal=1,
                title="조사",
                goal="정책 조사",
                status="ready",
                requested_by=ids["account"],
            )
        )
        session.execute(
            insert(metadata.tables["result"]).values(
                id=ids["result"],
                project_id=ids["project"],
                source_conversation_id=ids["child"],
                source_task_id=ids["task"],
                title="조사 결과",
            )
        )
        session.execute(
            insert(metadata.tables["result_revision"]).values(
                **revision_values(ids, id=ids["result_revision"])
            )
        )
        session.execute(
            update(metadata.tables["result"])
            .where(metadata.tables["result"].c.id == ids["result"])
            .values(latest_revision_id=ids["result_revision"], latest_version=1)
        )
        session.execute(
            insert(metadata.tables["resource"]).values(
                id=ids["resource"],
                project_id=ids["project"],
                kind="text",
                latest_revision_id=ids["resource_revision"],
                created_by=ids["account"],
            )
        )
        session.execute(
            insert(metadata.tables["resource_revision"]).values(
                id=ids["resource_revision"],
                resource_id=ids["resource"],
                number=1,
                name="정책",
                description="가상 정책",
                content="내용 v1",
                content_hash="0" * 64,
                created_by=ids["account"],
            )
        )
    yield ids


def test_active_work_and_summary_are_exclusive_per_contract(database: Database, records: dict) -> None:
    ids = records
    with database.transaction() as session:
        session.execute(insert(metadata.tables["run"]).values(**run_values(ids)))
        # A summary and work can coexist in the same conversation; only like targets conflict.
        session.execute(
            insert(metadata.tables["run"]).values(
                **run_values(ids, purpose="summary", target_id=ids["result"])
            )
        )
    for overrides, constraint in [
        ({}, "uq_run_active_work_conversation"),
        (
            {"purpose": "summary", "target_id": ids["result"], "status": "running"},
            "uq_run_active_summary_target",
        ),
    ]:
        with pytest.raises(IntegrityError, match=constraint), database.transaction() as session:
            session.execute(insert(metadata.tables["run"]).values(**run_values(ids, **overrides)))
    with database.transaction() as session:
        session.execute(
            insert(metadata.tables["run"]).values(**run_values(ids, conversation_id=ids["target"]))
        )
        session.execute(insert(metadata.tables["run"]).values(**run_values(ids, status="failed")))


@pytest.mark.parametrize(
    "overrides,constraint",
    [
        ({"status": "ready"}, "ck_run_valid_status"),
        ({"purpose": "summary"}, "ck_run_purpose_target"),
        ({"input_snapshot": []}, "ck_run_snapshot_is_object"),
        ({"attempt": 0}, "ck_run_positive_attempt"),
        ({"credential_account_id": UUID(int=0)}, "fk_run_credential_account_id_account"),
    ],
)
def test_invalid_runs_are_rejected(
    database: Database, records: dict, overrides: dict, constraint: str
) -> None:
    with pytest.raises(IntegrityError, match=constraint), database.transaction() as session:
        session.execute(insert(metadata.tables["run"]).values(**run_values(records, **overrides)))


def test_membership_and_branch_identity_deduplicate(database: Database, records: dict) -> None:
    ids = records
    values = {"account_id": ids["account"], "project_id": ids["project"], "role": "editor"}
    with database.transaction() as session:
        session.execute(insert(metadata.tables["membership"]).values(**values))
    with pytest.raises(IntegrityError, match="pk_membership"), database.transaction() as session:
        session.execute(insert(metadata.tables["membership"]).values(**values))
    with (
        pytest.raises(IntegrityError, match="uq_task_source_run_id_ordinal"),
        database.transaction() as session,
    ):
        session.execute(
            insert(metadata.tables["task"]).values(
                id=uuid4(),
                source_conversation_id=ids["source"],
                child_conversation_id=ids["target"],
                source_run_id=ids["root_run"],
                ordinal=1,
                title="중복 분기",
                goal="조사",
                status="pending",
                requested_by=ids["account"],
            )
        )


def test_resource_head_changes_do_not_change_pinned_revision(database: Database, records: dict) -> None:
    ids = records
    new_revision = uuid4()
    with database.transaction() as session:
        session.execute(
            insert(metadata.tables["conversation_resource"]).values(
                conversation_id=ids["source"],
                resource_id=ids["resource"],
                revision_id=ids["resource_revision"],
                applied_by=ids["account"],
            )
        )
        session.execute(
            insert(metadata.tables["resource_revision"]).values(
                id=new_revision,
                resource_id=ids["resource"],
                number=2,
                name="정책",
                description="가상 정책",
                content="내용 v2",
                content_hash="1" * 64,
                base_revision_id=ids["resource_revision"],
                created_by=ids["account"],
            )
        )
        session.execute(
            update(metadata.tables["resource"])
            .where(metadata.tables["resource"].c.id == ids["resource"])
            .values(latest_revision_id=new_revision)
        )
    with database.transaction() as session:
        assert (
            session.scalar(
                select(metadata.tables["conversation_resource"].c.revision_id).where(
                    metadata.tables["conversation_resource"].c.conversation_id == ids["source"]
                )
            )
            == ids["resource_revision"]
        )
    with (
        pytest.raises(IntegrityError, match="uq_resource_revision_resource_id_number"),
        database.transaction() as session,
    ):
        session.execute(
            insert(metadata.tables["resource_revision"]).values(
                id=uuid4(),
                resource_id=ids["resource"],
                number=2,
                name="중복",
                description="",
                content="중복",
                content_hash="1" * 64,
                base_revision_id=ids["resource_revision"],
                created_by=ids["account"],
            )
        )
    with (
        pytest.raises(IntegrityError, match="fk_resource_latest_revision"),
        database.transaction() as session,
    ):
        session.execute(
            update(metadata.tables["resource"])
            .where(metadata.tables["resource"].c.id == ids["resource"])
            .values(latest_revision_id=uuid4())
        )


def test_result_versions_share_deduplication_and_input_replacement(database: Database, records: dict) -> None:
    ids = records
    shares = metadata.tables["share"]
    inputs = metadata.tables["conversation_input"]
    share = {
        "result_revision_id": ids["result_revision"],
        "target_conversation_id": ids["target"],
        "shared_by": ids["account"],
    }
    linked = {
        "conversation_id": ids["target"],
        "result_id": ids["result"],
        "result_revision_id": ids["result_revision"],
        "version": 1,
        "title_snapshot": "결과",
        "conclusion_snapshot": "v1",
        "source_snapshot": {},
        "origin": "share",
        "created_by": ids["account"],
    }
    with database.transaction() as session:
        session.execute(insert(shares).values(id=uuid4(), **share))
        session.execute(insert(inputs).values(id=uuid4(), **linked))
    with (
        pytest.raises(IntegrityError, match="uq_share_result_revision_id_target_conversation_id"),
        database.transaction() as session,
    ):
        session.execute(insert(shares).values(id=uuid4(), **share))
    with (
        pytest.raises(IntegrityError, match="uq_conversation_input_conversation_id_result_id"),
        database.transaction() as session,
    ):
        session.execute(insert(inputs).values(id=uuid4(), **linked))
    with (
        pytest.raises(IntegrityError, match="uq_result_revision_result_id_version"),
        database.transaction() as session,
    ):
        session.execute(insert(metadata.tables["result_revision"]).values(**revision_values(ids)))
    second = uuid4()
    with database.transaction() as session:
        session.execute(
            insert(metadata.tables["result_revision"]).values(
                **revision_values(ids, id=second, version=2, conclusion="v2")
            )
        )
        session.execute(
            update(inputs)
            .where(inputs.c.conversation_id == ids["target"])
            .values(result_revision_id=second, version=2, conclusion_snapshot="v2")
        )
    with database.transaction() as session:
        assert (
            session.scalar(
                select(inputs.c.result_revision_id).where(inputs.c.conversation_id == ids["target"])
            )
            == second
        )
    with (
        pytest.raises(IntegrityError, match="fk_conversation_input_pinned_revision"),
        database.transaction() as session,
    ):
        session.execute(update(inputs).where(inputs.c.conversation_id == ids["target"]).values(version=1))
    with pytest.raises(IntegrityError, match="fk_result_latest_revision"), database.transaction() as session:
        session.execute(
            update(metadata.tables["result"])
            .where(metadata.tables["result"].c.id == ids["result"])
            .values(latest_version=2)
        )


def test_child_can_reference_task_before_the_task_is_inserted(database: Database, records: dict) -> None:
    ids = records
    task_id, child_id = uuid4(), uuid4()
    with database.transaction() as session:
        session.execute(
            insert(metadata.tables["conversation"]).values(
                id=child_id,
                project_id=ids["project"],
                parent_id=ids["source"],
                task_id=task_id,
                title="새 하위 조사",
                origin="branch",
                created_by=ids["account"],
            )
        )
        session.flush()
        session.execute(
            insert(metadata.tables["task"]).values(
                id=task_id,
                source_conversation_id=ids["source"],
                child_conversation_id=child_id,
                source_run_id=ids["root_run"],
                ordinal=2,
                title="새 조사",
                goal="정책 조사",
                status="pending",
                requested_by=ids["account"],
            )
        )
    with database.transaction() as session:
        assert (
            session.scalar(
                select(metadata.tables["conversation"].c.task_id).where(
                    metadata.tables["conversation"].c.id == child_id
                )
            )
            == task_id
        )
    with (
        pytest.raises(IntegrityError, match="fk_conversation_task_id_task"),
        database.transaction() as session,
    ):
        session.execute(
            insert(metadata.tables["conversation"]).values(
                id=uuid4(),
                project_id=ids["project"],
                task_id=uuid4(),
                title="유효하지 않은 분기",
                origin="branch",
                created_by=ids["account"],
            )
        )


@pytest.mark.parametrize("table_name", ["run", "task", "result_draft"])
def test_failures_store_codes_and_json_parameters(database: Database, records: dict, table_name: str) -> None:
    table = metadata.tables[table_name]
    row_id = records[{"run": "root_run", "task": "task", "result_draft": "result"}[table_name]]
    identity = table.c.result_id if table_name == "result_draft" else table.c.id
    if table_name == "result_draft":
        with database.transaction() as session:
            session.execute(
                insert(table).values(
                    result_id=row_id,
                    status="generating",
                    base_version=0,
                    run_id=records["root_run"],
                    message_from_seq=1,
                    message_to_seq=2,
                )
            )
    assert "error_message" not in table.c
    with database.transaction() as session:
        session.execute(
            update(table)
            .where(identity == row_id)
            .values(
                status="failed",
                error_code="MODEL_RATE_LIMITED",
                error_params={"retry_after_seconds": 30},
            )
        )
    with database.transaction() as session:
        row = session.execute(
            select(table.c.error_code, table.c.error_params).where(identity == row_id)
        ).one()
        assert row.error_code == "MODEL_RATE_LIMITED"
        assert row.error_params == {"retry_after_seconds": 30}
