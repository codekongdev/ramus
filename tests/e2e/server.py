"""Run the real API against a migrated disposable database for browser tests.

Only the randomly named test database is created/dropped; existing workspace data is untouched.
The development mailer's output is consumed privately by the Playwright fixture.
"""

import os
import secrets
import subprocess
import sys
from pathlib import Path

import uvicorn
from ramus_api.main import create_app
from ramus_api.settings import Settings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main() -> None:
    settings = Settings()
    base = make_url(settings.database_url)
    name = f"ramus_test_e2e_{secrets.token_hex(6)}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    root = Path(__file__).resolve().parents[2]
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        try:
            database_url = base.set(database=name).render_as_string(hide_password=False)
            subprocess.run(
                [sys.executable, "-m", "alembic", "-c", str(root / "apps/api/alembic.ini"), "upgrade", "head"],
                env={**os.environ, "DATABASE_URL": database_url},
                check=True,
            )
            uvicorn.run(
                create_app(settings.model_copy(update={"database_url": database_url})),
                host="127.0.0.1",
                port=settings.api_port,
            )
        finally:
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        admin.dispose()


if __name__ == "__main__":
    main()
