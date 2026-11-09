"""Run the real API against a migrated disposable database for browser tests.

Only the randomly named test database is created/dropped; existing workspace data is untouched.
The development mailer's output is consumed privately by the Playwright fixture.
"""

import json
import os
import secrets
import subprocess
import sys
from base64 import urlsafe_b64encode
from pathlib import Path

import uvicorn
from pydantic import SecretStr
from ramus_api.main import create_app
from ramus_api.modules.access.application.errors import AI_KEY_INVALID, AccessRejected
from ramus_api.modules.execution.fakes.llm import FakeLLM
from ramus_api.settings import Settings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


class TestAiKeyValidator:
    """Only synthetic test keys are accepted; browser tests can never call OpenAI."""

    async def validate(self, api_key: str) -> None:
        if not api_key.startswith("valid-test-"):
            raise AccessRejected(AI_KEY_INVALID)


def main() -> None:
    settings = Settings()
    base = make_url(settings.database_url)
    name = f"ramus_test_e2e_{secrets.token_hex(6)}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    root = Path(__file__).resolve().parents[2]
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        try:
            database_url = base.set(database=name).render_as_string(hide_password=False)
            subprocess.run(
                [sys.executable, "-m", "alembic", "-c", str(root / "apps/api/alembic.ini"), "upgrade", "head"],
                env={**os.environ, "DATABASE_URL": database_url},
                check=True,
            )
            uvicorn.run(
                create_app(
                    settings.model_copy(update={
                        "database_url": database_url,
                        "secret_key": SecretStr(urlsafe_b64encode(secrets.token_bytes(32)).decode()),
                    }),
                    ai_key_validator=TestAiKeyValidator(),
                    llm_gateway=FakeLLM(work_json=json.dumps({
                        "mode": "branch", "reply": "경쟁사 조사를 시작합니다.",
                        "tasks": [{"title": "경쟁사 분석", "goal": "멤버십 정책 비교", "start_input": "멤버십 정책을 조사해 주세요."}],
                    }, ensure_ascii=False)),
                ),
                host="127.0.0.1",
                port=settings.api_port,
            )
        finally:
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        admin.dispose()


if __name__ == "__main__":
    main()
