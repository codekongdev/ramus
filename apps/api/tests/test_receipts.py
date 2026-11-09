import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ramus_api.shared.domain import BusinessError, fingerprint
from ramus_api.shared.infrastructure.database import Database
from ramus_api.shared.infrastructure.receipts import RequestReceiptRow, SqlIdempotentExecutor

pytestmark = pytest.mark.integration

SCOPE = "test.create-item"
THREADS = 8


class CountingOperation:
    """A thread-safe operation that records how many times it ran."""

    def __init__(self, response: dict[str, Any], delay: float = 0.0,
                 failure: Exception | None = None) -> None:
        self._response = response
        self._delay = delay
        self._failure = failure
        self._lock = threading.Lock()
        self.calls = 0

    def __call__(self, session: Session) -> dict[str, Any]:
        with self._lock:
            self.calls += 1
        session.execute(select(1))
        time.sleep(self._delay)
        if self._failure is not None:
            raise self._failure
        return self._response


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def receipt_count(database: Database, actor_id: str) -> int:
    with database.transaction() as session:
        statement = select(func.count()).select_from(RequestReceiptRow)
        return session.scalar(statement.where(RequestReceiptRow.actor_id == actor_id)) or 0


@pytest.fixture
def executor(database: Database) -> SqlIdempotentExecutor:
    return SqlIdempotentExecutor(database)


def test_replay_returns_stored_response_and_runs_operation_once(
    executor: SqlIdempotentExecutor, database: Database
) -> None:
    actor, key = unique("actor"), unique("key")
    operation = CountingOperation({"id": "item-1", "tags": ["a", "b"]})
    first = executor.execute_once(actor, SCOPE, key, {"name": "a", "n": 1}, operation)
    second = executor.execute_once(actor, SCOPE, key, {"n": 1, "name": "a"}, operation)
    assert first == second == {"id": "item-1", "tags": ["a", "b"]}
    assert operation.calls == 1
    with database.transaction() as session:
        row = session.scalar(select(RequestReceiptRow).where(RequestReceiptRow.actor_id == actor))
        assert row is not None
        assert row.scope == SCOPE and row.idempotency_key == key
        assert row.fingerprint == fingerprint({"name": "a", "n": 1})
        assert row.response == first
        assert row.created_at.tzinfo is not None


def test_same_key_with_different_payload_is_a_conflict(executor: SqlIdempotentExecutor) -> None:
    actor, key = unique("actor"), unique("key")
    operation = CountingOperation({"ok": True})
    executor.execute_once(actor, SCOPE, key, {"name": "a"}, operation)
    with pytest.raises(BusinessError) as raised:
        executor.execute_once(actor, SCOPE, key, {"name": "b"}, operation)
    assert raised.value.status == 409
    assert raised.value.code == "IDEMPOTENCY_CONFLICT"
    assert operation.calls == 1


def test_concurrent_requests_with_same_key_run_operation_exactly_once(
    executor: SqlIdempotentExecutor, database: Database
) -> None:
    actor, key = unique("actor"), unique("key")
    operation = CountingOperation({"id": "only-once"}, delay=0.3)
    barrier = threading.Barrier(THREADS)

    def request() -> dict[str, Any]:
        barrier.wait()
        return executor.execute_once(actor, SCOPE, key, {"name": "same"}, operation)

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        results = list(pool.map(lambda _: request(), range(THREADS)))

    assert operation.calls == 1
    assert results == [{"id": "only-once"}] * THREADS
    assert receipt_count(database, actor) == 1


def test_failed_operation_leaves_no_receipt_and_retry_runs_again(
    executor: SqlIdempotentExecutor, database: Database
) -> None:
    actor, key = unique("actor"), unique("key")
    failing = CountingOperation({}, failure=RuntimeError("controlled failure"))
    with pytest.raises(RuntimeError, match="controlled failure"):
        executor.execute_once(actor, SCOPE, key, {"name": "a"}, failing)
    assert receipt_count(database, actor) == 0

    succeeding = CountingOperation({"id": "after-retry"})
    assert executor.execute_once(actor, SCOPE, key, {"name": "a"}, succeeding) == {"id": "after-retry"}
    assert succeeding.calls == 1
    assert receipt_count(database, actor) == 1


def test_different_actors_with_same_key_are_independent(executor: SqlIdempotentExecutor) -> None:
    key = unique("shared-key")
    first_operation = CountingOperation({"owner": "first"})
    second_operation = CountingOperation({"owner": "second"})
    first = executor.execute_once(unique("actor"), SCOPE, key, {"name": "a"}, first_operation)
    second = executor.execute_once(unique("actor"), SCOPE, key, {"name": "b"}, second_operation)
    assert (first, second) == ({"owner": "first"}, {"owner": "second"})
    assert (first_operation.calls, second_operation.calls) == (1, 1)


def test_different_scopes_with_same_key_are_independent(executor: SqlIdempotentExecutor) -> None:
    actor, key = unique("actor"), unique("key")
    operations: list[Callable[[Session], dict[str, Any]]] = [
        CountingOperation({"scope": "one"}),
        CountingOperation({"scope": "two"}),
    ]
    first = executor.execute_once(actor, "scope.one", key, {"name": "a"}, operations[0])
    second = executor.execute_once(actor, "scope.two", key, {"name": "a"}, operations[1])
    assert (first, second) == ({"scope": "one"}, {"scope": "two"})


def test_first_response_is_json_normalized_like_the_replay(executor: SqlIdempotentExecutor) -> None:
    actor, key = unique("actor"), unique("key")
    operation = CountingOperation({"items": (1, 2)})
    first = executor.execute_once(actor, SCOPE, key, {}, operation)
    assert first == {"items": [1, 2]}
    assert executor.execute_once(actor, SCOPE, key, {}, operation) == first
