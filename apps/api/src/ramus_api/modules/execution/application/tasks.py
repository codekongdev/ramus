"""Authorized task reads and idempotent control of a task's current work run."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, Literal, Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.access.application.ports import ProjectAccess, TransactionFactory
from ramus_api.modules.conversations.application.ports import ConversationRepository
from ramus_api.modules.execution.application.control import RunControlService
from ramus_api.modules.execution.application.errors import MESSAGES, business_error
from ramus_api.shared.application.idempotency import IdempotentExecutor
from ramus_api.shared.domain.errors import BusinessError
from ramus_api.shared.presentation.error_messages import message_for

TransactionT = TypeVar("TransactionT")
TransactionT_contra = TypeVar("TransactionT_contra", contravariant=True)
Action = Literal["cancel", "retry"]


@dataclass(frozen=True)
class TaskRecord:
    id: UUID
    source_conversation_id: UUID
    child_conversation_id: UUID
    title: str
    goal: str
    status: str
    requested_by: UUID
    current_run_id: UUID | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    result_id: UUID | None


class TaskRepository(Protocol[TransactionT_contra]):
    def get(self, session: TransactionT_contra, task_id: UUID) -> TaskRecord | None: ...

    def list_for_conversation(
        self, session: TransactionT_contra, conversation_id: UUID
    ) -> tuple[TaskRecord, ...]: ...

    def lock_current_work_run(self, session: TransactionT_contra, task: TaskRecord) -> bool:
        """Lock only the Run and read the current Task pointer without taking its row lock."""
        ...

    def lock_current_task(self, session: TransactionT_contra, task: TaskRecord) -> bool:
        """Check the pointer under the Task lock, after acquiring any active-run uniqueness lock."""
        ...


def task_json(task: TaskRecord) -> dict[str, Any]:
    error = None
    if task.error_code is not None:
        code = task.error_code if task.error_code in MESSAGES else "LLM_UNAVAILABLE"
        error = {"code": code, "message": message_for(code)}
    return {
        "id": str(task.id),
        "source_conversation_id": str(task.source_conversation_id),
        "child_conversation_id": str(task.child_conversation_id),
        "title": task.title,
        "goal": task.goal,
        "status": task.status,
        "requested_by": str(task.requested_by),
        "result_id": str(task.result_id) if task.result_id else None,
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "error": error,
    }


class TaskService(Generic[TransactionT]):
    def __init__(
        self,
        *,
        transaction: TransactionFactory[TransactionT],
        tasks: TaskRepository[TransactionT],
        conversations: ConversationRepository[TransactionT],
        access: ProjectAccess[TransactionT],
        idempotency: IdempotentExecutor[TransactionT],
        control: RunControlService | None,
    ) -> None:
        self._transaction = transaction
        self._tasks = tasks
        self._conversations = conversations
        self._access = access
        self._idempotency = idempotency
        self._control = control

    def _require_conversation(self, session: TransactionT, conversation_id: UUID, actor_id: UUID) -> None:
        conversation = self._conversations.get_conversation(session, conversation_id)
        if conversation is None:
            raise business_error("NOT_FOUND")
        self._access.require_member(session, conversation.project_id, actor_id)

    def _require_task(self, session: TransactionT, task_id: UUID, actor_id: UUID) -> TaskRecord:
        task = self._tasks.get(session, task_id)
        if task is None:
            raise business_error("NOT_FOUND")
        self._require_conversation(session, task.source_conversation_id, actor_id)
        return task

    @staticmethod
    def _require_owner(task: TaskRecord, actor_id: UUID) -> None:
        if task.requested_by != actor_id:
            raise business_error("FORBIDDEN")

    def list_tasks(self, conversation_id: UUID, actor_id: UUID) -> dict[str, Any]:
        with self._transaction() as session:
            self._require_conversation(session, conversation_id, actor_id)
            return {"items": [task_json(task) for task in self._tasks.list_for_conversation(session, conversation_id)]}

    def get_task(self, task_id: UUID, actor_id: UUID) -> dict[str, Any]:
        with self._transaction() as session:
            return task_json(self._require_task(session, task_id, actor_id))

    def change(self, task_id: UUID, actor_id: UUID, action: Action, key: str) -> dict[str, Any]:
        # Replaying a receipt must not grant access after project membership was revoked.
        with self._transaction() as session:
            task = self._require_task(session, task_id, actor_id)
            self._require_owner(task, actor_id)

        def operation(session: TransactionT) -> dict[str, Any]:
            task = self._require_task(session, task_id, actor_id)
            self._require_owner(task, actor_id)
            if not self._tasks.lock_current_work_run(session, task):
                raise business_error("RUN_NOT_CANCELLABLE" if action == "cancel" else "RUN_NOT_RETRYABLE")
            if self._control is None:
                raise BusinessError("SERVICE_UNAVAILABLE", message_for("SERVICE_UNAVAILABLE"), status=503)

            def ensure_current(_state=None) -> None:
                if not self._tasks.lock_current_task(session, task):
                    raise business_error("RUN_NOT_CANCELLABLE" if action == "cancel" else "RUN_NOT_RETRYABLE")

            if action == "cancel":
                ensure_current()
                self._control.cancel(session, task.current_run_id, actor_id)
            else:
                self._control.retry(session, task.current_run_id, actor_id, validate_requeued=ensure_current)
            return task_json(self._require_task(session, task_id, actor_id))

        return self._idempotency.execute_once(str(actor_id), f"tasks.{action}:{task_id}", key, {}, operation)
