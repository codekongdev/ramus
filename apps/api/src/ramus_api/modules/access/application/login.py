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

from ramus_api.modules.access.application.email_delivery import DELIVERY_LEASE, EmailDeliveryStore
from ramus_api.modules.access.application.errors import (
    AUTH_CODE_EXPIRED,
    AUTH_CODE_INVALID,
    AUTH_RATE_LIMITED,
    SERVICE_UNAVAILABLE,
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
    TransactionFactory,
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
    transactions: TransactionFactory[T]
    deliveries: EmailDeliveryStore[T]

    async def __call__(self, email: str, key: str, ip: str = "unknown") -> datetime:
        """Reserve, send outside the transaction, then activate a successfully delivered code.

        A receipt points to durable delivery state, so replay cannot silently turn a failed or
        interrupted send into success. Codes remain only in memory until their hash is activated.
        """
        await asyncio.to_thread(self.limits.check, "request", email, ip)
        payload = {"email": email}
        result = await asyncio.to_thread(
            self.idempotency.execute_once, ANONYMOUS_ACTOR, EMAIL_CODE_SCOPE, key, payload,
            partial(self._prepare_delivery, email),
        )
        # Receipts created before delivery tracking contained only this successful response.
        if "delivery_id" not in result:
            return _stored_datetime(result, "resend_available_at")
        delivery_id = UUID(result["delivery_id"])
        code = self.secrets.new_code()
        claim = await asyncio.to_thread(self._claim_delivery, email, delivery_id, code)
        if claim.attempt_id is None:
            assert claim.resend_available_at is not None
            return claim.resend_available_at
        failed = False
        try:
            await self.mailer.send_code(email, code)
        except asyncio.CancelledError:
            # SMTP may still be running in a thread. Keep its lease until it can be reclaimed.
            raise
        except Exception:
            failed = True
        if failed:
            try:
                await asyncio.to_thread(self._fail_delivery, email, delivery_id, claim.attempt_id)
            except Exception:
                # A storage outage leaves the durable lease reclaimable. Never chain a mail
                # provider's exception (which may contain a code) into a server traceback.
                raise AccessRejected(SERVICE_UNAVAILABLE) from None
            raise AccessRejected(SERVICE_UNAVAILABLE) from None
        completed = await asyncio.to_thread(self._complete_delivery, email, delivery_id, claim.attempt_id)
        if completed is None:
            raise AccessRejected(SERVICE_UNAVAILABLE)
        return completed

    def _prepare_delivery(self, email: str, transaction: T) -> JsonObject:
        self.codes.lock_email(transaction, email)
        now = self.clock.now()
        last_created_at = self.codes.latest_created_at(transaction, email)
        if last_created_at is not None and not can_resend(last_created_at, now):
            available_at = to_iso_utc(resend_available_at(last_created_at))
            raise AccessRejected(AUTH_RATE_LIMITED, {"resend_available_at": available_at})
        delivery_id = new_id()
        self.deliveries.prepare(transaction, delivery_id, email, now)
        return {"delivery_id": str(delivery_id)}

    def _claim_delivery(self, email: str, delivery_id: UUID, code: str):
        with self.transactions() as transaction:
            self.codes.lock_email(transaction, email)
            now, code_id, attempt_id = self.clock.now(), new_id(), new_id()
            value = NewEmailCode(code_id, email, hash_code(code, str(code_id), self.secret), now, code_expires_at(now))
            return self.deliveries.claim(transaction, delivery_id, email, value, attempt_id, now, now + DELIVERY_LEASE)

    def _fail_delivery(self, email: str, delivery_id: UUID, attempt_id: UUID) -> None:
        with self.transactions() as transaction:
            self.codes.lock_email(transaction, email)
            self.deliveries.fail(transaction, delivery_id, attempt_id)

    def _complete_delivery(self, email: str, delivery_id: UUID, attempt_id: UUID) -> datetime | None:
        with self.transactions() as transaction:
            self.codes.lock_email(transaction, email)
            return self.deliveries.complete(transaction, delivery_id, attempt_id, self.clock.now())


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
