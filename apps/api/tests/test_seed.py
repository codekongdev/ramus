"""Exercise the actual seed CLI, including racing separate processes."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from sqlalchemy import MetaData, create_engine, insert, select, update

from ramus_api.modules.access.infrastructure.models import AccountRow
from ramus_api.modules.conversations.infrastructure.models import MessageRow
from ramus_api.modules.projects.infrastructure.models import ProjectRow
from ramus_api.modules.projects.infrastructure.sample import SHARED_SAMPLE_PROJECT_ID, SHARED_SAMPLE_SEED_KEY
from ramus_api.modules.resources.domain.models import ResourceKind
from ramus_api.modules.resources.domain.rules import content_hash, normalize_content
from ramus_api.modules.resources.infrastructure.models import ResourceRevisionRow, ResourceRow
from ramus_api.modules.seed.domain.content import AUTHORS, RESEARCH, RESOURCES, sample_id
from ramus_api.modules.seed.infrastructure.models import SeedMarkerRow
from ramus_api.modules.seed.infrastructure.sample import SHARED_SAMPLE_MARKER_KEY, prepare_shared_sample
from ramus_api.shared.infrastructure.database import Database

ROOT = Path(__file__).resolve().parents[3]
CONTENT_MARKER_KEY = "ramus:shared-sample:membership:content"


def test_shared_project_id_is_a_stable_uuid5() -> None:
    assert SHARED_SAMPLE_PROJECT_ID == uuid5(NAMESPACE_URL, SHARED_SAMPLE_SEED_KEY)
    assert SHARED_SAMPLE_PROJECT_ID.version == 5


def cli(database_url: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "ramus_api.modules.seed"],
        env={**os.environ, "DATABASE_URL": database_url},
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def snapshot(engine) -> dict[str, list[dict]]:
    """Compare IDs and full persisted values, including timestamps and version snapshots."""
    metadata = MetaData()
    metadata.reflect(engine)
    with engine.connect() as connection:
        return {
            name: sorted(
                [dict(row) for row in connection.execute(select(table)).mappings()],
                key=lambda row: json.dumps(row, sort_keys=True, default=str),
            )
            for name, table in metadata.tables.items()
        }


@pytest.mark.integration
def test_seed_cli_is_concurrent_idempotent_and_preserves_user_changes(
    fresh_database_url, run_alembic
) -> None:
    run_alembic(fresh_database_url, "upgrade", "head")
    # Independent processes race their first insert into an empty migrated database.
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(cli, [fresh_database_url] * 6))
    assert responses == [{"project_id": str(SHARED_SAMPLE_PROJECT_ID)}] * 6
    engine = create_engine(fresh_database_url)
    try:
        initial = snapshot(engine)
        assert {name: len(initial[name]) for name in (
            "project", "seed_marker", "account", "conversation", "message", "resource", "resource_revision",
            "conversation_resource", "task", "run", "result", "result_revision", "share", "conversation_input",
        )} == {
            "project": 2, "seed_marker": 2, "account": 4, "conversation": 4, "message": 10,
            "resource": 3, "resource_revision": 3, "conversation_resource": 12, "task": 3, "run": 4,
            "result": 3, "result_revision": 3, "share": 3, "conversation_input": 3,
        }
        assert {row["key"] for row in initial["seed_marker"]} == {SHARED_SAMPLE_MARKER_KEY, CONTENT_MARKER_KEY}
        assert {row["version"] for row in initial["seed_marker"]} == {1}
        assert {row["id"] for row in initial["account"]} == {sample_id(f"author:{author.key}") for author in AUTHORS}
        assert {row["id"] for row in initial["conversation"]} == {
            sample_id("conversation:design"), *(sample_id(f"conversation:{research.key}") for research in RESEARCH),
        }
        assert {row["id"] for row in initial["resource_revision"]} == {
            sample_id(f"resource:{resource.key}:v1") for resource in RESOURCES
        }
        assert {row["id"] for row in initial["result_revision"]} == {
            sample_id(f"result:{research.key}:v1") for research in RESEARCH
        }
        assert {row["status"] for row in initial["task"]} == {"ready"}
        assert {row["status"] for row in initial["run"]} == {"succeeded"}
        labels = {author.label for author in AUTHORS}
        assert all(row["example_author_label"] in labels for row in initial["message"])
        design_id = sample_id("conversation:design")
        assert len([row for row in initial["message"] if row["conversation_id"] == design_id]) == 1
        assert {row["conversation_id"] for row in initial["conversation_input"]} == {design_id}
        for revision in initial["result_revision"]:
            source = revision["source"]
            messages = [row for row in initial["message"] if row["conversation_id"] == source["conversation_id"]]
            # JSON snapshots encode UUIDs as strings.
            if not messages:
                messages = [row for row in initial["message"] if str(row["conversation_id"]) == source["conversation_id"]]
            assert source["message_from_seq"] == min(row["seq"] for row in messages)
            assert source["message_to_seq"] == max(row["seq"] for row in messages)
            assert set(source["resource_revision_ids"]) == {
                str(sample_id(f"resource:{resource.key}:v1")) for resource in RESOURCES
            }
        assert cli(fresh_database_url) == responses[0]
        assert snapshot(engine) == initial
        with engine.begin() as connection:
            connection.execute(update(ProjectRow).where(ProjectRow.id == SHARED_SAMPLE_PROJECT_ID).values(name="팀이 수정한 이름"))
            user_id = uuid4()
            connection.execute(insert(AccountRow).values(id=user_id, email="sample-user@example.test", display_name="실제 참여자"))
            connection.execute(insert(MessageRow).values(
                id=uuid4(), conversation_id=design_id, author_kind="human", author_account_id=user_id,
                body="팀원이 이어서 작성한 정책 논의입니다.",
            ))
            revision_id = uuid4()
            resource_id = sample_id("resource:benchmark-skill")
            content = normalize_content(ResourceKind.SKILL, name="팀에서 수정한 조사 스킬", description="실제 수정",
                                        instructions="실제 팀의 추가 조사 기준", content=None, file_name=None)
            connection.execute(insert(ResourceRevisionRow).values(
                id=revision_id, resource_id=resource_id, number=2, name=content.name,
                description=content.description, instructions=content.instructions, content=None, file_name=None,
                content_hash=content_hash(content), base_revision_id=sample_id("resource:benchmark-skill:v1"),
                created_by=user_id,
            ))
            connection.execute(update(ResourceRow).where(ResourceRow.id == resource_id).values(latest_revision_id=revision_id))
        edited = snapshot(engine)
        assert cli(fresh_database_url) == responses[0]
        assert snapshot(engine) == edited
    finally:
        engine.dispose()


@pytest.mark.integration
def test_seed_identity_collision_rolls_back_without_overwriting(fresh_database_url, run_alembic) -> None:
    run_alembic(fresh_database_url, "upgrade", "head")
    database = Database(fresh_database_url)
    try:
        with database.transaction() as session:
            session.execute(
                insert(ProjectRow).values(
                    id=SHARED_SAMPLE_PROJECT_ID, name="기존 프로젝트", is_shared_sample=False
                )
            )
        with pytest.raises(RuntimeError, match="identity"):
            prepare_shared_sample(database)
        with database.transaction() as session:
            assert session.get(ProjectRow, SHARED_SAMPLE_PROJECT_ID).name == "기존 프로젝트"
            assert session.get(SeedMarkerRow, SHARED_SAMPLE_MARKER_KEY) is None
    finally:
        database.dispose()
