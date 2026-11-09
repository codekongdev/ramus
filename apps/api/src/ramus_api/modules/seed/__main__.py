"""Prepare the fixed shared project: ``python -m ramus_api.modules.seed``."""

import argparse
import json

from ramus_api.modules.seed.infrastructure.sample import prepare_shared_sample
from ramus_api.settings import Settings
from ramus_api.shared.infrastructure.database import Database


def main() -> None:
    argparse.ArgumentParser(
        description="Create the fixed shared sample project without resetting data."
    ).parse_args()
    database = Database(Settings().database_url)
    try:
        project_id = prepare_shared_sample(database)
    finally:
        database.dispose()
    print(json.dumps({"project_id": str(project_id)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
