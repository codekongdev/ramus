import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect


def test_explicit_migration_and_seed_are_repeatable_without_data_loss(tmp_path):
    root = Path(__file__).resolve().parents[3]
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    env = {**os.environ, "DATABASE_URL": database_url}

    def run(*arguments):
        return subprocess.run(
            [sys.executable, *arguments], cwd=root, env=env, check=True, capture_output=True, text=True,
        )

    run("-m", "alembic", "-c", "apps/api/alembic.ini", "upgrade", "head")
    run("-m", "ramus_api.seed")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        users = connection.exec_driver_sql("SELECT id FROM users ORDER BY id").all()
        projects = connection.exec_driver_sql("SELECT id FROM projects ORDER BY id").all()
    run("-m", "alembic", "-c", "apps/api/alembic.ini", "upgrade", "head")
    run("-m", "ramus_api.seed")
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT id FROM users ORDER BY id").all() == users
        assert connection.exec_driver_sql("SELECT id FROM projects ORDER BY id").all() == projects
        assert len(users) == 2 and len(projects) == 1
    run("-m", "alembic", "-c", "apps/api/alembic.ini", "check")
    run("-m", "alembic", "-c", "apps/api/alembic.ini", "downgrade", "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()
