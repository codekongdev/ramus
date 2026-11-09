"""Explicitly add local demo users and a project without DDL or data reset."""

from ramus_api.application.workspace import Workspace
from ramus_api.composition import SqlUnitOfWork
from ramus_api.infrastructure.database import Database
from ramus_api.settings import Settings


def main() -> None:
    database = Database(Settings().database_url)
    try:
        Workspace(SqlUnitOfWork(database)).ensure_demo()
    finally:
        database.close()
    print("Ramus demo seed is ready. Existing projects were preserved.")


if __name__ == "__main__":
    main()
