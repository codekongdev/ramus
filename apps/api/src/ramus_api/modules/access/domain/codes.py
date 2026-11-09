"""Login code and session rules (docs/contracts.md 1.1). Pure functions; no framework imports.

Only digests are stored. A code digest mixes in a per-row salt (the code row ID) so equal codes in
different rows have different digests; a session token is already 256 bits of randomness, so a plain
SHA-256 is enough to make a leaked table useless for logging in.
"""

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

CODE_LENGTH = 6
CODE_SPACE = 10**CODE_LENGTH
CODE_TTL = timedelta(minutes=10)
MAX_CODE_ATTEMPTS = 5
RESEND_INTERVAL = timedelta(seconds=60)
SESSION_TTL = timedelta(days=14)


class CodeVerdict(StrEnum):
    """Result of checking a submitted code. ``EXPIRED`` covers missing, used, timed-out, and exhausted."""

    VERIFIED = "verified"
    INVALID = "invalid"
    EXPIRED = "expired"


@dataclass(frozen=True)
class EmailCodeState:
    """The stored state of the latest code for an email address."""

    id: UUID
    code_hash: str
    expires_at: datetime
    attempts: int
    consumed_at: datetime | None


def format_code(number: int) -> str:
    """Zero-pads a random number in ``[0, 10**CODE_LENGTH)`` to a fixed-width code."""
    if not 0 <= number < CODE_SPACE:
        raise ValueError(f"A login code must be in [0, {CODE_SPACE})")
    return f"{number:0{CODE_LENGTH}d}"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_code(code: str, salt: str, secret: str = "") -> str:
    value = f"ramus.email-code:{salt}:{code}"
    if secret:
        return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()
    return _sha256(value)


def hash_session_token(token: str) -> str:
    return _sha256(f"ramus.session:{token}")


def code_expires_at(created_at: datetime) -> datetime:
    return created_at + CODE_TTL


def session_expires_at(issued_at: datetime) -> datetime:
    return issued_at + SESSION_TTL


def resend_available_at(last_created_at: datetime) -> datetime:
    return last_created_at + RESEND_INTERVAL


def can_resend(last_created_at: datetime | None, now: datetime) -> bool:
    return last_created_at is None or now >= resend_available_at(last_created_at)


def judge_code(state: EmailCodeState | None, submitted: str, now: datetime, secret: str = "") -> CodeVerdict:
    """Checks ``submitted`` against the latest code. Usability is checked before the digest."""
    if state is None or state.consumed_at is not None:
        return CodeVerdict.EXPIRED
    if now >= state.expires_at or state.attempts >= MAX_CODE_ATTEMPTS:
        return CodeVerdict.EXPIRED
    if hmac.compare_digest(hash_code(submitted, str(state.id), secret), state.code_hash):
        return CodeVerdict.VERIFIED
    return CodeVerdict.INVALID


def to_iso_utc(moment: datetime) -> str:
    """ISO 8601 in UTC with a ``Z`` suffix, matching how responses serialize datetimes."""
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")
