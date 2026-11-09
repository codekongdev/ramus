import json
from pathlib import Path


def test_exported_contract_matches_the_actual_api(app):
    root = Path(__file__).resolve().parents[3]
    assert json.loads((root / "contracts/openapi.json").read_text()) == app.openapi()
