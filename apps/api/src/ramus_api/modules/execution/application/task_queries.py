"""Read-only task use cases with project authorization through public ports."""

from typing import Any, Protocol
from uuid import UUID

from ramus_api.modules.conversations.application.ports import ConversationRepository, ProjectAccess
from ramus_api.modules.execution.application.errors import business_error
from ramus_api.modules.execution.application.runtime_ports import TransactionFactory


class TaskQueryStore(Protocol):
    def get(self, session: Any, task_id: UUID) -> dict | None: ...

    def list_for_conversation(self, session: Any, conversation_id: UUID) -> list[dict]: ...


class TaskQueries:
    def __init__(
        self, transaction: TransactionFactory[Any], tasks: TaskQueryStore,
        conversations: ConversationRepository[Any], access: ProjectAccess[Any],
    ) -> None:
        self._transaction, self._tasks = transaction, tasks
        self._conversations, self._access = conversations, access

    def _authorize(self, session: Any, conversation_id: UUID, account_id: UUID) -> None:
        conversation = self._conversations.get_conversation(session, conversation_id)
        if conversation is None:
            raise business_error("NOT_FOUND")
        self._access.require_member(session, conversation.project_id, account_id)

    def get(self, task_id: UUID, account_id: UUID) -> dict:
        with self._transaction() as session:
            task = self._tasks.get(session, task_id)
            if task is None:
                raise business_error("NOT_FOUND")
            self._authorize(session, task["source_conversation_id"], account_id)
            return task

    def list(self, conversation_id: UUID, account_id: UUID) -> dict:
        with self._transaction() as session:
            self._authorize(session, conversation_id, account_id)
            return {"items": self._tasks.list_for_conversation(session, conversation_id)}
