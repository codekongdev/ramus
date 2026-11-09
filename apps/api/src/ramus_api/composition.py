from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from sqlalchemy.orm import Session

from ramus_api.application.ports import WorkContext
from ramus_api.infrastructure.database import Database
from ramus_api.infrastructure.receipts import execute_once
from ramus_api.modules.access.infrastructure import AccessRepository
from ramus_api.modules.conversations.infrastructure import ConversationRepository


@dataclass
class SqlWorkContext:
    access: AccessRepository
    conversations: ConversationRepository


def context(session: Session) -> SqlWorkContext:
    return SqlWorkContext(AccessRepository(session), ConversationRepository(session))


class SqlUnitOfWork:
    def __init__(self, database: Database):
        self.database = database

    @contextmanager
    def transaction(self) -> Iterator[SqlWorkContext]:
        with self.database.transaction() as session:
            yield context(session)

    def execute_once(
        self,
        actor_id: str,
        scope: str,
        request_id: str,
        payload: dict,
        operation: Callable[[WorkContext], dict],
        authorize: Callable[[WorkContext], None] | None = None,
        authorize_response: Callable[[WorkContext, dict], None] | None = None,
    ) -> dict:
        return execute_once(
            self.database,
            actor_id,
            scope,
            request_id,
            payload,
            lambda session: operation(context(session)),
            (lambda session: authorize(context(session))) if authorize else None,
            (lambda session, response: authorize_response(context(session), response)) if authorize_response else None,
        )
