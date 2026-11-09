from typing import Protocol
from uuid import UUID


class CredentialProvider(Protocol):
    """Executor-only access. Never store its return value in a run, event, or log."""

    def get_api_key(self, account_id: UUID) -> str: ...


class Mailer(Protocol):
    async def send_code(self, email: str, code: str) -> None: ...
