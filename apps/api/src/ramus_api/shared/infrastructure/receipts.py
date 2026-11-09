"""PostgreSQL-backed idempotency receipts.

A receipt is inserted and flushed in the same transaction as the operation, before the operation's
side effects. The unique constraint on ``(actor_id, scope, idempotency_key)`` makes concurrent
requests with the same key wait for the first one; when it commits they fail with IntegrityError and
replay the stored response. If the operation fails, the receipt rolls back with it and a retry runs
the operation again.
"""

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, String, UniqueConstraint, Uuid, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from ramus_api.shared.application import JsonObject
from ramus_api.shared.application.idempotency import ExecutionResult
from ramus_api.shared.domain import fingerprint, idempotency_conflict, new_id, utc_now
from ramus_api.shared.infrastructure.database import Base, Database

Operation = Callable[[Session], JsonObject]


class RequestReceiptRow(Base):
    __tablename__ = "request_receipt"
    __table_args__ = (UniqueConstraint("actor_id", "scope", "idempotency_key"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(64))
    scope: Mapped[str] = mapped_column(String(100))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class _ConcurrentReceipt(Exception):
    """Another transaction committed a receipt with the same identity first."""


def _normalize_response(response: object) -> JsonObject:
    """Round-trips through JSON so the first response equals every later replay."""
    normalized = json.loads(json.dumps(response, ensure_ascii=False))
    if not isinstance(normalized, dict):
        raise TypeError(f"Idempotent operations must return a JSON object, got {type(response).__name__}")
    return normalized


def _replay(row: RequestReceiptRow, expected_fingerprint: str) -> JsonObject:
    if row.fingerprint != expected_fingerprint:
        raise idempotency_conflict()
    return row.response


class SqlIdempotentExecutor:
    """``IdempotentExecutor`` implementation whose operations receive a SQLAlchemy ``Session``."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def execute_once(
        self,
        actor_id: str,
        scope: str,
        key: str,
        payload: Mapping[str, Any],
        operation: Operation,
    ) -> JsonObject:
        """Runs ``operation`` at most once per ``(actor_id, scope, key)`` and replays its response.

        Usage rule: ``operation`` must be a short database-only step inside this transaction. Do not
        call external services (AI models, HTTP APIs, mail) from it. The receipt's unique-index lock is
        held until the operation finishes, so a slow operation blocks every request with the same key
        and holds a pooled connection for its whole duration. For AI work, the operation only
        registers a run; the executor performs the model call separately (roadmap section 3).
        """
        return self.execute_with_status(actor_id, scope, key, payload, operation).response

    def execute_with_status(
        self, actor_id: str, scope: str, key: str, payload: Mapping[str, Any], operation: Operation
    ) -> ExecutionResult:
        identity = (actor_id, scope, key)
        expected = fingerprint(payload)
        try:
            with self._database.transaction() as session:
                existing = _find(session, identity)
                if existing is not None:
                    return ExecutionResult(_replay(existing, expected), replayed=True)
                receipt = _claim(session, identity, expected)
                response = _normalize_response(operation(session))
                receipt.response = response
                session.flush()
                return ExecutionResult(response, replayed=False)
        except _ConcurrentReceipt as concurrent:
            return self._replay_committed(identity, expected, concurrent)

    def _replay_committed(
        self, identity: tuple[str, str, str], expected: str, concurrent: _ConcurrentReceipt
    ) -> ExecutionResult:
        with self._database.transaction() as session:
            existing = _find(session, identity)
            if existing is None:
                raise concurrent.__cause__ or concurrent
            return ExecutionResult(_replay(existing, expected), replayed=True)


def _find(session: Session, identity: tuple[str, str, str]) -> RequestReceiptRow | None:
    actor_id, scope, key = identity
    statement = select(RequestReceiptRow).where(
        RequestReceiptRow.actor_id == actor_id,
        RequestReceiptRow.scope == scope,
        RequestReceiptRow.idempotency_key == key,
    )
    return session.scalar(statement)


def _claim(session: Session, identity: tuple[str, str, str], expected: str) -> RequestReceiptRow:
    actor_id, scope, key = identity
    receipt = RequestReceiptRow(
        id=new_id(),
        actor_id=actor_id,
        scope=scope,
        idempotency_key=key,
        fingerprint=expected,
        response={},
        created_at=utc_now(),
    )
    session.add(receipt)
    try:
        session.flush()  # Claim the key before any side effect of the operation.
    except IntegrityError as error:
        raise _ConcurrentReceipt() from error
    return receipt
