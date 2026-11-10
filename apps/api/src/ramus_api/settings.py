"""Runtime configuration read from the environment and the repository-root ``.env`` file.

Environment variables take priority over ``.env``; a missing ``.env`` file is allowed.
Empty values are treated as unset.
"""

import secrets
from pathlib import Path
from typing import Literal

from pydantic import EmailStr, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATABASE_URL = "postgresql+psycopg://ramus:ramus-local@127.0.0.1:55432/ramus"
DEFAULT_API_PORT = 8000
DEFAULT_WEB_PORT = 5173
MIN_PORT = 1
MAX_PORT = 65535
_PROCESS_AUTH_SECRET = secrets.token_hex(32)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,  # `RAMUS_API_PORT=` means "unset", matching vite.config.ts.
        frozen=True,
    )

    # Set a stable secret in deployed environments; the local fallback changes on process restart.
    auth_secret: SecretStr = Field(
        default=SecretStr(_PROCESS_AUTH_SECRET), min_length=32, validation_alias="RAMUS_AUTH_SECRET"
    )
    database_url: str = DEFAULT_DATABASE_URL
    api_port: int = Field(
        default=DEFAULT_API_PORT, ge=MIN_PORT, le=MAX_PORT, validation_alias="RAMUS_API_PORT"
    )
    web_port: int = Field(
        default=DEFAULT_WEB_PORT, ge=MIN_PORT, le=MAX_PORT, validation_alias="RAMUS_WEB_PORT"
    )
    # Adds ``Secure`` to the session cookie. Turn on wherever the app is served over HTTPS.
    cookie_secure: bool = Field(default=False, validation_alias="RAMUS_COOKIE_SECURE")
    secret_key: SecretStr | None = Field(default=None, validation_alias="RAMUS_SECRET_KEY")
    openai_model: str = Field(default="gpt-6-luna", min_length=1, validation_alias="OPENAI_MODEL")
    environment: Literal["development", "test", "staging", "production"] = Field(
        default="development", validation_alias="RAMUS_ENV"
    )
    email_code_auth_enabled: bool = Field(default=False, validation_alias="RAMUS_EMAIL_CODE_AUTH_ENABLED")
    mailer_backend: Literal["logging", "smtp"] = Field(default="logging", validation_alias="RAMUS_MAILER")
    smtp_host: str | None = Field(default=None, min_length=1, validation_alias="RAMUS_SMTP_HOST")
    smtp_port: int = Field(default=587, ge=MIN_PORT, le=MAX_PORT, validation_alias="RAMUS_SMTP_PORT")
    smtp_security: Literal["starttls", "tls"] = Field(default="starttls", validation_alias="RAMUS_SMTP_SECURITY")
    smtp_username: str | None = Field(default=None, min_length=1, validation_alias="RAMUS_SMTP_USERNAME")
    smtp_password: SecretStr | None = Field(default=None, validation_alias="RAMUS_SMTP_PASSWORD")
    smtp_from: EmailStr | None = Field(default=None, validation_alias="RAMUS_SMTP_FROM")
    smtp_timeout: float = Field(default=10.0, gt=0, le=30, validation_alias="RAMUS_SMTP_TIMEOUT")

    @property
    def uses_ephemeral_auth_secret(self) -> bool:
        """Deployment assembly can reject the process-local development fallback."""
        return self.auth_secret.get_secret_value() == _PROCESS_AUTH_SECRET
