"""Runtime configuration read from the environment and the repository-root ``.env`` file.

Environment variables take priority over ``.env``; a missing ``.env`` file is allowed.
Empty values are treated as unset.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATABASE_URL = "postgresql+psycopg://ramus:ramus-local@127.0.0.1:55432/ramus"
DEFAULT_API_PORT = 8000
DEFAULT_WEB_PORT = 5173
MIN_PORT = 1
MAX_PORT = 65535


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,  # `RAMUS_API_PORT=` means "unset", matching vite.config.ts.
        frozen=True,
    )

    database_url: str = DEFAULT_DATABASE_URL
    api_port: int = Field(default=DEFAULT_API_PORT, ge=MIN_PORT, le=MAX_PORT, validation_alias="RAMUS_API_PORT")
    web_port: int = Field(default=DEFAULT_WEB_PORT, ge=MIN_PORT, le=MAX_PORT, validation_alias="RAMUS_WEB_PORT")
    # Adds ``Secure`` to the session cookie. Turn on wherever the app is served over HTTPS.
    cookie_secure: bool = Field(default=False, validation_alias="RAMUS_COOKIE_SECURE")
