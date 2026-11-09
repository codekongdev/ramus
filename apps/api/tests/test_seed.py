"""Exercise the actual seed CLI, including racing separate processes."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
from sqlalchemy import create_engine, insert, select, update

from ramus_api.modules.projects.infrastructure.models import ProjectRow
from ramus_api.modules.projects.infrastructure.sample import SHARED_SAMPLE_PROJECT_ID, SHARED_SAMPLE_SEED_KEY
from ramus_api.modules.seed.infrastructure.models import SeedMarkerRow
from ramus_api.modules.seed.infrastructure.sample import SHARED_SAMPLE_MARKER_KEY, prepare_shared_sample
from ramus_api.shared.infrastructure.database import Database

ROOT = Path(__file__).resolve().parents[3]


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
        with engine.begin() as connection:
            projects = connection.execute(select(ProjectRow.__table__)).mappings().all()
            markers = connection.execute(select(SeedMarkerRow.__table__)).mappings().all()
            assert len(projects) == len(markers) == 1
            assert projects[0]["seed_key"] == SHARED_SAMPLE_SEED_KEY
            assert markers[0]["key"] == SHARED_SAMPLE_MARKER_KEY
            assert markers[0]["version"] == 1
            created_at = projects[0]["created_at"]
            connection.execute(update(ProjectRow).values(name="팀이 수정한 이름"))
        assert cli(fresh_database_url) == responses[0]
        with engine.connect() as connection:
            row = connection.execute(select(ProjectRow.__table__)).mappings().one()
            assert row["name"] == "팀이 수정한 이름"
            assert row["created_at"] == created_at
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
