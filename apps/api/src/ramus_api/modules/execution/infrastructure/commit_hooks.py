"""Post-commit callbacks and savepoints for SQLAlchemy sessions.

SQLAlchemy dispatches ``after_commit`` for savepoint releases too, so callbacks are held until the
outermost transaction commits. A rollback drops the callbacks registered inside the rolled-back
transaction (a savepoint or the whole transaction). Callback errors are logged, never raised: the data
is already committed and the caller must not see a failure.
"""

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session, SessionTransaction

logger = logging.getLogger(__name__)

_PENDING = "ramus.execution.after_commit"

Pending = tuple[tuple[SessionTransaction, Callable[[], None]], ...]


def _pending(session: Session) -> Pending:
    return session.info.get(_PENDING, ())


def _within(transaction: SessionTransaction | None, ancestor: SessionTransaction) -> bool:
    while transaction is not None:
        if transaction is ancestor:
            return True
        transaction = transaction.parent
    return False


def _on_commit(session: Session) -> None:
    if session.in_nested_transaction():
        return
    callbacks = _pending(session)
    session.info[_PENDING] = ()
    for _, callback in callbacks:
        try:
            callback()
        except Exception as error:  # noqa: BLE001 - committed data must not look failed to the caller
            logger.error("Post-commit callback failed: error=%s", type(error).__name__)


def _on_soft_rollback(session: Session, previous: SessionTransaction) -> None:
    session.info[_PENDING] = tuple(entry for entry in _pending(session) if not _within(entry[0], previous))


class SqlAlchemyTransactionHooks:
    def after_commit(self, session: Session, callback: Callable[[], None]) -> None:
        if not event.contains(session, "after_commit", _on_commit):
            event.listen(session, "after_commit", _on_commit)
            event.listen(session, "after_soft_rollback", _on_soft_rollback)
        transaction = session.get_nested_transaction() or session.get_transaction()
        if transaction is None:
            raise RuntimeError("after_commit requires an active transaction")
        session.info[_PENDING] = (*_pending(session), (transaction, callback))

    def savepoint(self, session: Session) -> AbstractContextManager[Any]:
        return session.begin_nested()
