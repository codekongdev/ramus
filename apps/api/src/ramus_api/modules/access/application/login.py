"""Email-code login use cases: request a code and verify it.

Both run through the idempotency executor with the ``anonymous`` actor (docs/contracts.md 1).
The plaintext code never enters a receipt, a table, a response, or an error detail.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from typing import Any, Generic, TypeVar
from uuid import UUID

from ramus_api.modules.access.application.errors import (
    AUTH_CODE_EXPIRED,
    AUTH_CODE_INVALID,
    AUTH_RATE_LIMITED,
    AccessRejected,
)
from ramus_api.modules.access.application.ports import (
    AccountStore,
    Clock,
    EmailCodeStore,
    Mailer,
    NewEmailCode,
    SecretSource,
    SharedProjectProvider,
)
from ramus_api.modules.access.application.rate_limits import AuthRateLimiter
from ramus_api.modules.access.application.sessions import IssuedSession, SessionIssuer
from ramus_api.modules.access.domain.codes import (
    CodeVerdict,
    can_resend,
    code_expires_at,
    hash_code,
    judge_code,
    resend_available_at,
    to_iso_utc,
)
from ramus_api.modules.access.domain.email import display_name_for
from ramus_api.modules.access.domain.models import MembershipRole
from ramus_api.shared.application import IdempotentExecutor, JsonObject
from ramus_api.shared.domain import new_id

T = TypeVar("T")

ANONYMOUS_ACTOR = "anonymous"
EMAIL_CODE_SCOPE = "auth.email_code"
VERIFY_SCOPE = "auth.verify"


def _stored_field(response: JsonObject, name: str) -> Any:
    if name not in response:
        raise ValueError(f"Stored login response is missing {name!r}")
    return response[name]


def _stored_datetime(response: JsonObject, name: str) -> datetime:
    return datetime.fromisoformat(_stored_field(response, name))


@dataclass(frozen=True)
class RequestEmailCode(Generic[T]):
    idempotency: IdempotentExecutor[T]
    codes: EmailCodeStore[T]
    mailer: Mailer
    clock: Clock
    secrets: SecretSource
    limits: AuthRateLimiter[T]
    secret: str = field(repr=False)

    async def __call__(self, email: str, key: str, ip: str = "unknown") -> datetime:
        """Stores a new code and mails it. Returns when the next code may be requested.

        Raises ``AccessRejected`` (``AUTH_RATE_LIMITED``) within the resend interval. Mail goes out
        only after the receipt and code row commit, because the executor forbids external calls
        inside the operation. A mailer failure propagates (500); the stored code stays unused.
        """
        await asyncio.to_thread(self.limits.check, "request", email, ip)
        code = self.secrets.new_code()
        operation = partial(self._store_code, email, code)
        payload = {"email": email}
        result = await asyncio.to_thread(
            self.idempotency.execute_with_status, ANONYMOUS_ACTOR, EMAIL_CODE_SCOPE, key, payload, operation
        )
        if not result.replayed:
            await self.mailer.send_code(email, code)
        return _stored_datetime(result.response, "resend_available_at")

    def _store_code(self, email: str, code: str, transaction: T) -> JsonObject:
        self.codes.lock_email(transaction, email)
        now = self.clock.now()
        last_created_at = self.codes.latest_created_at(transaction, email)
        if last_created_at is not None and not can_resend(last_created_at, now):
            available_at = to_iso_utc(resend_available_at(last_created_at))
            raise AccessRejected(AUTH_RATE_LIMITED, {"resend_available_at": available_at})
        code_id = new_id()
        digest = hash_code(code, str(code_id), self.secret)
        self.codes.add(transaction, NewEmailCode(code_id, email, digest, now, code_expires_at(now)))
        return {"resend_available_at": to_iso_utc(resend_available_at(now))}


@dataclass(frozen=True)
class VerifyEmailCode(Generic[T]):
    idempotency: IdempotentExecutor[T]
    codes: EmailCodeStore[T]
    accounts: AccountStore[T]
    shared_project: SharedProjectProvider[T]
    issuer: SessionIssuer[T]
    clock: Clock
    limits: AuthRateLimiter[T]
    secret: str = field(repr=False)

    def __call__(self, email: str, code: str, key: str, ip: str = "unknown") -> IssuedSession:
        """Checks the code, joins the shared project, and issues a new session.

        The check returns its outcome as JSON instead of raising, so a failed attempt's counter
        increment commits together with its receipt rather than rolling back.

        The session is issued in a separate transaction after the receipt commits, on every call
        including replays. A client that lost the first response and retries with the same key still
        receives a cookie, as long as the code's validity window has not passed. Replays are limited to three session issuances per receipt, including the original,
        within the code's 10-minute lifetime.
        """
        self.limits.check("verify", email, ip)
        payload = {"email": email, "code_hmac": hash_code(code, email, self.secret)}
        operation = partial(self._check_code, email, code)
        outcome = self.idempotency.execute_once(ANONYMOUS_ACTOR, VERIFY_SCOPE, key, payload, operation)
        account_id = self._accepted_account(outcome)
        self.limits.check("session", email, ip, key=key)
        return self.issuer.issue(account_id)

    def _check_code(self, email: str, code: str, transaction: T) -> JsonObject:
        self.codes.lock_email(transaction, email)
        state = self.codes.lock_latest(transaction, email)
        now = self.clock.now()
        verdict = judge_code(state, code, now, self.secret)
        if state is None or verdict is CodeVerdict.EXPIRED:
            return {"outcome": CodeVerdict.EXPIRED.value}
        if verdict is CodeVerdict.INVALID:
            self.codes.record_failed_attempt(transaction, state.id)
            return {"outcome": CodeVerdict.INVALID.value}
        self.codes.consume(transaction, state.id, now)
        account_id = self.accounts.ensure_account(transaction, email, display_name_for(email))
        project_id = self.shared_project.ensure_shared_project(transaction)
        self.accounts.add_membership(transaction, account_id, project_id, MembershipRole.EDITOR)
        for followup_id in self.shared_project.existing_followup_project_ids(transaction):
            self.accounts.add_membership(transaction, account_id, followup_id, MembershipRole.EDITOR)
        return {
            "outcome": CodeVerdict.VERIFIED.value,
            "account_id": str(account_id),
            "session_issuable_until": to_iso_utc(state.expires_at),
        }

    def _accepted_account(self, outcome: JsonObject) -> UUID:
        verdict = CodeVerdict(_stored_field(outcome, "outcome"))
        if verdict is CodeVerdict.INVALID:
            raise AccessRejected(AUTH_CODE_INVALID)
        if verdict is CodeVerdict.EXPIRED:
            raise AccessRejected(AUTH_CODE_EXPIRED)
        if self.clock.now() >= _stored_datetime(outcome, "session_issuable_until"):
            raise AccessRejected(AUTH_CODE_EXPIRED)
        return UUID(_stored_field(outcome, "account_id"))
