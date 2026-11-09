"""Prepare the fixed shared project: ``python -m ramus_api.modules.seed``."""

import argparse
import json
from uuid import UUID

from ramus_api.modules.seed.infrastructure.sample import prepare_shared_sample
from ramus_api.settings import Settings
from ramus_api.shared.infrastructure.database import Database


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare shared fictional sample content; normal runs preserve work.")
    parser.add_argument("--reset", action="store_true", help="Operator only: clear both sample project contents.")
    parser.add_argument("--confirm-project-id", type=UUID, help="Exact shared project ID required for reset.")
    parser.add_argument("--work-preserved", action="store_true", help="Confirm existing work has been backed up or may be removed.")
    args = parser.parse_args()
    if args.reset != (args.confirm_project_id is not None) or args.work_preserved != args.reset:
        parser.error("Reset requires --reset --confirm-project-id <shared-project-id> --work-preserved together")
    database = Database(Settings().database_url)
    try:
        project_id = prepare_shared_sample(
            database, reset_project_id=args.confirm_project_id, work_preserved=args.work_preserved,
        )
    except (ValueError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")
    finally:
        database.dispose()
    print(json.dumps({"project_id": str(project_id)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
