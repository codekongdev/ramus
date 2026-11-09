"""Shared fixtures.

Integration tests never touch the database named in ``DATABASE_URL``. They create a throwaway
``ramus_test_<random>`` database on the same server, migrate it with Alembic, and drop it afterwards.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError

from ramus_api.settings import Settings
from ramus_api.shared.infrastructure.database import Database

API_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = API_ROOT / "alembic.ini"
TEST_DATABASE_PREFIX = "ramus_test_"
ADMIN_DATABASE = "postgres"
INTEGRATION_MARKER = "integration: requires a running PostgreSQL server (start it with `pnpm db:up`)"

AlembicRunner = Callable[..., subprocess.CompletedProcess[str]]


def pytest_configure(config: pytest.Config) -> None:
    # Also registered in pyproject.toml; repeated here because running pytest from the repository root
    # does not read apps/api/pyproject.toml.
    config.addinivalue_line("markers", INTEGRATION_MARKER)


def _render(url: URL) -> str:
    return url.render_as_string(hide_password=False)


class PostgresServer:
    """Creates and drops temporary databases through the ``postgres`` admin database."""

    def __init__(self, base_url: URL, admin: Engine) -> None:
        self._base_url = base_url
        self._admin = admin

    @contextmanager
    def temporary_database(self) -> Iterator[str]:
        name = f"{TEST_DATABASE_PREFIX}{secrets.token_hex(6)}"
        with self._admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        try:
            yield _render(self._base_url.set(database=name))
        finally:
            self._drop(name)

    def _drop(self, name: str) -> None:
        if not name.startswith(TEST_DATABASE_PREFIX):
            raise ValueError(f"Refusing to drop non-test database {name!r}")
        with self._admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


@pytest.fixture(scope="session")
def postgres_server() -> Iterator[PostgresServer]:
    base_url = make_url(Settings().database_url)
    admin = create_engine(base_url.set(database=ADMIN_DATABASE), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as error:
        admin.dispose()
        target = f"{base_url.host}:{base_url.port}"
        pytest.fail(
            f"PostgreSQL에 연결할 수 없습니다({target}). 저장소 루트에서 `pnpm db:up`을 실행한 뒤 "
            f"다시 테스트하세요. 원인: {type(error.orig).__name__}",
            pytrace=False,
        )
    try:
        yield PostgresServer(base_url, admin)
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def run_alembic() -> AlembicRunner:
    """Runs the Alembic CLI in a subprocess, exactly as a developer would from the repository root."""

    def run(database_url: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *arguments],
            env={**os.environ, "DATABASE_URL": database_url},
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            pytest.fail(f"alembic {' '.join(arguments)} failed:\n{result.stdout}\n{result.stderr}")
        return result

    return run


@pytest.fixture(scope="session")
def database_url(postgres_server: PostgresServer, run_alembic: AlembicRunner) -> Iterator[str]:
    """A migrated temporary database shared by the whole test session."""
    with postgres_server.temporary_database() as url:
        run_alembic(url, "upgrade", "head")
        yield url


@pytest.fixture
def fresh_database_url(postgres_server: PostgresServer) -> Iterator[str]:
    """An empty, unmigrated temporary database for a single test."""
    with postgres_server.temporary_database() as url:
        yield url


@pytest.fixture
def database(database_url: str) -> Iterator[Database]:
    instance = Database(database_url)
    try:
        yield instance
    finally:
        instance.dispose()


@pytest.fixture
def integration_settings(database_url: str) -> Settings:
    return Settings(_env_file=None, database_url=database_url)


@pytest.fixture
def unit_settings() -> Settings:
    """Settings for tests that never open a database connection."""
    return Settings(_env_file=None)
