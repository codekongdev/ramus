"""Conversation use cases. Adapters own I/O; every mutation owns one idempotent transaction."""

from typing import Any, Generic, TypeVar
from uuid import UUID

from ramus_api.modules.access.application.ports import TransactionFactory
from ramus_api.modules.conversations.application.ports import (
    CommittedEvents,
    ConversationRepository,
    ProjectAccess,
    RunReader,
)
from ramus_api.modules.conversations.domain.errors import ConversationNotFound
from ramus_api.modules.conversations.domain.models import AuthorKind
from ramus_api.modules.conversations.domain.views import (
    ConversationRecord,
    ancestor_paths,
    conversation_json,
    mentions_ai,
    message_json,
    validate_text,
)
from ramus_api.modules.execution.application.ports import RunRequester
from ramus_api.modules.execution.domain.models import RunPurpose, RunRequest
from ramus_api.modules.realtime.domain.events import EventName, ProjectEvent
from ramus_api.shared.application.idempotency import IdempotentExecutor
from ramus_api.shared.domain.primitives import utc_now

TransactionT = TypeVar("TransactionT")


class ConversationService(Generic[TransactionT]):
    def __init__(
        self,
        transaction_factory: TransactionFactory[TransactionT],
        repository: ConversationRepository[TransactionT],
        access: ProjectAccess[TransactionT],
        idempotency: IdempotentExecutor[TransactionT],
        requester: RunRequester[TransactionT],
        runs: RunReader[TransactionT],
        events: CommittedEvents[TransactionT],
    ) -> None:
        self._transaction = transaction_factory
        self._repository = repository
        self._access = access
        self._idempotency = idempotency
        self._requester = requester
        self._runs = runs
        self._events = events

    def _require_conversation(
        self, session: TransactionT, conversation_id: UUID, account_id: UUID, *, lock: bool = False
    ) -> ConversationRecord:
        conversation = self._repository.get_conversation(session, conversation_id, lock=lock)
        if conversation is None:
            raise ConversationNotFound()
        self._access.require_member(session, conversation.project_id, account_id)
        return conversation

    def _conversation_json(
        self, session: TransactionT, conversation: ConversationRecord
    ) -> dict[str, Any]:
        records = self._repository.list_conversations(session, conversation.project_id)
        return conversation_json(conversation, ancestor_paths(records)[conversation.id])

    def list_conversations(
        self, project_id: UUID, account_id: UUID, q: str = "", exclude_id: UUID | None = None
    ) -> dict[str, Any]:
        with self._transaction() as session:
            self._access.require_member(session, project_id, account_id)
            records = self._repository.list_conversations(session, project_id)
            paths = ancestor_paths(records)
            query = q.casefold()
            return {
                "items": [
                    conversation_json(item, paths[item.id])
                    for item in records
                    if item.id != exclude_id and query in item.title.casefold()
                ]
            }

    def get_conversation(self, conversation_id: UUID, account_id: UUID) -> dict[str, Any]:
        with self._transaction() as session:
            conversation = self._require_conversation(session, conversation_id, account_id)
            response = self._conversation_json(session, conversation)
            response["active_run"] = self._runs.active_run(session, conversation_id)
            return response

    def create_conversation(
        self, project_id: UUID, account_id: UUID, title: str, key: str
    ) -> dict[str, Any]:
        validate_text(title, 100)
        # A receipt is a stored response, not an authorization grant after membership is revoked.
        with self._transaction() as session:
            self._access.require_member(session, project_id, account_id)

        def operation(session: TransactionT) -> dict[str, Any]:
            self._access.require_member(session, project_id, account_id)
            conversation = self._repository.create_top(session, project_id, title, account_id)
            response = conversation_json(conversation, ())
            self._events.after_commit(
                session,
                ProjectEvent(
                    project_id,
                    EventName.CONVERSATION_CREATED,
                    utc_now(),
                    {"project_id": project_id, "conversation": response},
                ),
            )
            return response

        return self._idempotency.execute_once(
            str(account_id), f"conversations.create:{project_id}", key, {"title": title}, operation
        )

    def list_messages(
        self,
        conversation_id: UUID,
        account_id: UUID,
        after_seq: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        if (after_seq is not None and after_seq < 0) or not 1 <= limit <= 200:
            raise ValueError("Invalid message cursor or page size")
        with self._transaction() as session:
            self._require_conversation(session, conversation_id, account_id)
            records = self._repository.list_messages(session, conversation_id, after_seq or 0, limit + 1)
            names = self._access.display_names(
                session, {item.author_account_id for item in records if item.author_account_id is not None}
            )
            page = records[:limit]
            return {
                "items": [message_json(item, names) for item in page],
                "next_after_seq": page[-1].seq if len(records) > limit else None,
            }

    def post_message(
        self, conversation_id: UUID, account_id: UUID, body: str, key: str
    ) -> dict[str, Any]:
        validate_text(body, 20_000)
        with self._transaction() as session:
            self._require_conversation(session, conversation_id, account_id)

        def operation(session: TransactionT) -> dict[str, Any]:
            # Execution finishes while holding its run row before writing an AI message. Register
            # runs before taking the conversation lock to keep that same lock order and avoid a
            # pending-run unique-index wait deadlocking with the finisher's message append.
            conversation = self._require_conversation(session, conversation_id, account_id)
            run = None
            run_id = None
            if mentions_ai(body):
                reference = self._requester.request(
                    session,
                    RunRequest(
                        conversation.project_id,
                        conversation_id,
                        conversation.task_id,
                        RunPurpose.WORK,
                        None,
                        account_id,
                    ),
                )
                run_id = reference.run_id
                run = self._runs.get_run(session, run_id)
            message = self._repository.append_message(
                session,
                conversation_id,
                body,
                AuthorKind.HUMAN,
                author_account_id=account_id,
                requested_by=account_id if run_id else None,
                run_id=run_id,
            )
            names = self._access.display_names(session, {account_id})
            response = {"message": message_json(message, names), "run": run}
            self._events.after_commit(
                session,
                ProjectEvent(
                    conversation.project_id,
                    EventName.MESSAGE_CREATED,
                    utc_now(),
                    {"conversation_id": conversation_id, "message_id": message.id, "seq": message.seq},
                ),
            )
            return response

        return self._idempotency.execute_once(
            str(account_id), f"messages.create:{conversation_id}", key, {"body": body}, operation
        )
