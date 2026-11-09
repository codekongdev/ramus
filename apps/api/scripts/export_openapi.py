"""Writes the OpenAPI contract to ``contracts/openapi.json`` at the repository root.

Run from the repository root: ``pnpm api:openapi``.
"""

import argparse
import sys
from pathlib import Path

from ramus_api.main import create_app
from ramus_api.openapi_export import render_openapi
from ramus_api.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = REPO_ROOT / "contracts" / "openapi.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="file to write")
    arguments = parser.parse_args(argv)
    # create_app opens no database connection; _env_file=None keeps local .env values out of the contract.
    document = render_openapi(create_app(Settings(_env_file=None)))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(document, encoding="utf-8")
    print(f"wrote {arguments.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
