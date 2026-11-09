"""Application-level port for running a change at most once per idempotency key."""

from collections.abc import Callable, Mapping
from typing import Any, Protocol, TypeVar

JsonObject = dict[str, Any]

TransactionT = TypeVar("TransactionT")


class IdempotentExecutor(Protocol[TransactionT]):
    """Runs ``operation`` once per ``(actor_id, scope, key)`` and replays its stored response.

    ``operation`` receives the open transaction so its side effects commit or roll back together
    with the receipt. Raises ``BusinessError`` (409 ``IDEMPOTENCY_CONFLICT``) when the same key is
    reused with a different payload. ``operation`` must be a short DB-only step with no external calls
    (no AI/HTTP); see ``SqlIdempotentExecutor.execute_once`` for why.
    """

    def execute_once(
        self,
        actor_id: str,
        scope: str,
        key: str,
        payload: Mapping[str, Any],
        operation: Callable[[TransactionT], JsonObject],
    ) -> JsonObject: ...
