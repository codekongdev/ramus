"""Creates the E2E database if it is missing and migrates it to head.

Run with the API's environment: ``uv run --project apps/api python tests/e2e/support/prepare_db.py``.
The target comes from ``DATABASE_URL``; its database name must start with ``ramus_e2e`` so this script
can never migrate or create the development database by mistake.
"""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "apps" / "api" / "alembic.ini"
REQUIRED_PREFIX = "ramus_e2e"


def main() -> int:
    url = make_url(os.environ["DATABASE_URL"])
    name = url.database or ""
    if not name.startswith(REQUIRED_PREFIX):
        print(f"refusing to prepare {name!r}: E2E database names must start with {REQUIRED_PREFIX!r}", file=sys.stderr)
        return 2
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            exists = connection.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name})
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{name}"'))
                print(f"created database {name}")
    finally:
        admin.dispose()
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"],
        check=True,
        env=os.environ,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
