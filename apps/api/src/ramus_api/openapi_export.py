"""Deterministic OpenAPI rendering shared by ``scripts/export_openapi.py`` and the drift test."""

import json

from fastapi import FastAPI

INDENT = 2


def render_openapi(app: FastAPI) -> str:
    """Sorted keys, two-space indent, UTF-8 text, trailing newline. Never touches the database."""
    return json.dumps(app.openapi(), indent=INDENT, sort_keys=True, ensure_ascii=False) + "\n"
