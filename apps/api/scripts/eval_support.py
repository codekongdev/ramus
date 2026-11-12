"""Shared helpers for the Ramus evaluation scripts: API key lookup and a static credential provider.

The key is read only from an explicit dotenv-style file or the environment and is never printed,
logged or written.
"""

import os
import sys
from pathlib import Path
from uuid import UUID


class StaticCredentials:
    """CredentialProvider returning a fixed string; the value is never printed or stored."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def get_api_key(self, account_id: UUID) -> str:
        return self._api_key


def read_env_key(path: Path, name: str = "OPENAI_API_KEY") -> str | None:
    """Return only the requested entry from a dotenv-style file; all other entries are ignored."""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export "):].lstrip()
        key, sep, value = stripped.partition("=")
        if not sep or key.strip() != name:
            continue
        value = value.strip()
        if value[:1] in {'"', "'"} and value.count(value[0]) >= 2:
            return value[1:value.index(value[0], 1)] or None
        return value.split(" #", 1)[0].strip() or None
    return None


def resolve_api_key(env_file: str | None) -> str:
    try:
        key = read_env_key(Path(env_file), "OPENAI_API_KEY") if env_file else os.environ.get("OPENAI_API_KEY")
    except (OSError, UnicodeDecodeError):
        # No path, error text or file content: those could expose secrets.
        sys.exit("Live mode could not read the --env-file; check that it exists and is a UTF-8 text file.")
    if not key:
        source = "the --env-file" if env_file else "the environment"
        sys.exit(f"Live mode needs OPENAI_API_KEY, but it was not found in {source}.")
    return key
