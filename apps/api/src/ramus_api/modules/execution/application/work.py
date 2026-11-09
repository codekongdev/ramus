"""The work-purpose use case: one answer, clarification, or an atomic fan-out of child tasks."""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from pydantic import ValidationError

from ramus_api.modules.conversations.application.ports import ConversationWriter
from ramus_api.modules.conversations.application.work_inputs import WorkInputReader
from ramus_api.modules.conversations.domain.models import AuthorKind, NewChildConversation, NewMessage
from ramus_api.modules.execution.application.branch_ports import BranchTaskStore, NewBranchTask
from ramus_api.modules.execution.application.output_schema import ChildWorkOutput, ParentWorkOutput
from ramus_api.modules.execution.application.ports import ContextProvider, RunRequester
from ramus_api.modules.execution.domain.models import (
    ConversationContext,
    LlmFailure,
    LlmRequest,
    RunError,
    RunPurpose,
    RunRequest,
    RunView,
)
from ramus_api.modules.execution.domain.work import WorkHistory, build_work_request
from ramus_api.shared.domain.primitives import new_id


def _mutable_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _mutable_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_mutable_json(item) for item in value]
    return value


class WorkPurposeHandler:
    purpose = RunPurpose.WORK.value

    def __init__(
        self,
        *,
        inputs: WorkInputReader[Any],
        writer: ConversationWriter[Any],
        tasks: BranchTaskStore[Any],
        contexts: ContextProvider[Any],
        requester: RunRequester[Any],
    ) -> None:
        self._inputs, self._writer, self._tasks = inputs, writer, tasks
        self._contexts, self._requester = contexts, requester

    def _history(self, session: Any, run: RunView) -> WorkHistory:
        history = self._inputs.read(session, run.conversation_id, run.id)
        if history.project_id != run.project_id or history.task_id != run.task_id:
            raise ValueError("Work run does not match its conversation")
        if not history.messages or history.messages[-1].run_id != run.id:
            raise ValueError("Work input must end at its original request")
        if run.task_id is not None and not history.is_child:
            raise ValueError("Task work must belong to a child conversation")
        return history

    def build_request(self, session: Any, run: RunView, context: ConversationContext) -> LlmRequest:
        history = self._history(session, run)
        if run.task_id is not None:
            history = replace(history, goal=self._tasks.goal(session, run.task_id))
        return build_work_request(run, context, history)

    def complete(self, session: Any, run: RunView, output: Mapping[str, Any]) -> None:
        history = self._history(session, run)
        model = ChildWorkOutput if history.is_child else ParentWorkOutput
        try:
            parsed = model.model_validate(_mutable_json(output))
        except (ValidationError, ValueError, TypeError):
            raise LlmFailure("LLM_OUTPUT_INVALID") from None
        if parsed.mode != "branch":
            self._append(session, run, parsed.reply)
            return
        assert isinstance(parsed, ParentWorkOutput)
        self._inputs.lock_parent(session, run.conversation_id)
        # Read the parent's applied set once. Later children copy the first uncommitted child,
        # so even a concurrent parent resource application cannot split siblings across versions.
        inheritance_source = run.conversation_id
        for ordinal, task in enumerate(parsed.tasks, start=1):
            task_id = new_id()
            child_id = self._writer.create_child(
                session,
                NewChildConversation(run.project_id, run.conversation_id, task_id, task.title, run.requested_by),
            )
            self._tasks.create(
                session,
                NewBranchTask(task_id, run.conversation_id, child_id, run.id, ordinal, task.title, task.goal, run.requested_by),
            )
            self._contexts.copy_resources(session, inheritance_source, child_id)
            inheritance_source = child_id
            child_run = self._requester.request(
                session,
                RunRequest(run.project_id, child_id, task_id, RunPurpose.WORK, None, run.requested_by),
            )
            self._writer.append_message(
                session,
                NewMessage(child_id, AuthorKind.SYSTEM, task.start_input, run.requested_by, child_run.run_id),
            )
        self._append(session, run, f"별도 작업 {len(parsed.tasks)}개로 나눠 진행합니다.")

    def _append(self, session: Any, run: RunView, body: str) -> None:
        self._writer.append_message(
            session, NewMessage(run.conversation_id, AuthorKind.AI, body, run.requested_by, run.id)
        )

    def fail(self, session: Any, run: RunView, error: RunError) -> None:
        # RunAnnouncer projects failure/recovery to Task; no failed response is written as AI content.
        pass
