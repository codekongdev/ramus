"""Process-level adapters: wall clock and cryptographic randomness."""

import secrets
from datetime import datetime

from ramus_api.modules.access.domain.codes import CODE_SPACE, format_code
from ramus_api.shared.domain import utc_now

SESSION_TOKEN_BYTES = 32


class SystemClock:
    def now(self) -> datetime:
        return utc_now()


class SystemSecretSource:
    def new_code(self) -> str:
        return format_code(secrets.randbelow(CODE_SPACE))

    def new_session_token(self) -> str:
        return secrets.token_urlsafe(SESSION_TOKEN_BYTES)
