"""Export the actual API schema without connecting to the database."""
from __future__ import annotations

import json
from pathlib import Path

from ramus_api.main import app

root = Path(__file__).resolve().parents[1]
target = root / "contracts" / "openapi.json"
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n")
print("Exported contracts/openapi.json")
