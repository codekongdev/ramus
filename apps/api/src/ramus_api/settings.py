from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )
    database_url: str = "postgresql+psycopg://ramus:ramus-local@127.0.0.1:55433/ramus"
    ramus_cookie_secure: bool = False
    ramus_allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
    )

    @property
    def allowed_origins(self) -> set[str]:
        return {part.strip() for part in self.ramus_allowed_origins.split(",") if part.strip()}
