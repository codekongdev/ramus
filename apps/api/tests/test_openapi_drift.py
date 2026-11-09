"""The committed contracts/openapi.json must equal what the app generates."""

from __future__ import annotations

import json
from pathlib import Path

from ramus_api.main import create_app
from ramus_api.openapi_export import render_openapi
from ramus_api.settings import Settings

OPENAPI_PATH = Path(__file__).resolve().parents[3] / "contracts" / "openapi.json"


def test_committed_openapi_matches_the_app() -> None:
    generated = render_openapi(create_app(Settings(_env_file=None)))
    committed = OPENAPI_PATH.read_text(encoding="utf-8") if OPENAPI_PATH.exists() else ""
    assert committed == generated, (
        "contracts/openapi.json is out of date. Run `pnpm gen:api` from the repository root and commit "
        "contracts/openapi.json and apps/web/src/api/schema.d.ts."
    )


def test_rendering_is_deterministic_and_well_formed() -> None:
    first = render_openapi(create_app(Settings(_env_file=None)))
    second = render_openapi(create_app(Settings(_env_file=None)))
    assert first == second
    assert first.endswith("}\n")
    document = json.loads(first)
    assert document["openapi"].startswith("3.")
    assert list(document) == sorted(document)
