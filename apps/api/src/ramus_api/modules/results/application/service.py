"""Result summaries and immutable approvals. The caller owns each database transaction."""

from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from ramus_api.modules.access.application.ports import ProjectAccess
from ramus_api.modules.conversations.application.ports import (
    CommittedEvents,
    ConversationRepository,
    RunReader,
)
from ramus_api.modules.conversations.application.summary_inputs import SummaryInputReader
from ramus_api.modules.execution.application.ports import ContextProvider, RunRequester
from ramus_api.modules.execution.application.summary_tasks import SummaryTaskReader
from ramus_api.modules.execution.domain.models import ConversationContext, ResultInput, RunPurpose, RunRequest
from ramus_api.modules.results.application.errors import rejected
from ramus_api.modules.results.application.events import result_event
from ramus_api.modules.results.application.ports import ResultRepository
from ramus_api.modules.results.domain.records import ResultRecord, Revision, Source
from ramus_api.shared.domain.primitives import new_id


@dataclass(frozen=True)
class ResultService:
    repository: ResultRepository[Any]
    tasks: SummaryTaskReader[Any]
    conversations: ConversationRepository[Any]
    inputs: SummaryInputReader[Any]
    contexts: ContextProvider[Any]
    access: ProjectAccess[Any]
    requester: RunRequester[Any]
    runs: RunReader[Any]
    events: CommittedEvents[Any]

    def _require(self, session, actor_id, result_id, *, lock=False) -> ResultRecord:
        result = self.repository.get(session, result_id, lock=lock)
        if result is None:
            raise rejected("NOT_FOUND")
        self.access.require_member(session, result.project_id, actor_id)
        return self._normalized(session, result)

    def _normalized(self, session, result: ResultRecord) -> ResultRecord:
        # The executor deliberately does not call purpose handlers on cancellation. Reading
        # a cancelled run therefore projects a recoverable failed draft without writing on GET.
        if result.draft is not None and result.draft.status == "generating":
            run = self.runs.get_run(session, result.draft.run_id)
            if run["status"] in ("failed", "cancelled", "succeeded"):
                error = run.get("error")
                draft = replace(result.draft, status="failed", conclusion=None,
                                error_code=error["code"] if error else "RUN_INTERRUPTED")
                return replace(result, draft=draft)
        return result

    def get(self, session, actor_id: UUID, result_id: UUID) -> ResultRecord:
        return self._require(session, actor_id, result_id)

    def revision(self, session, actor_id: UUID, revision_id: UUID) -> Revision:
        revision = self.repository.revision(session, revision_id)
        if revision is None:
            raise rejected("NOT_FOUND")
        self._require(session, actor_id, revision.result_id)
        return revision

    def summarize(self, session, actor_id: UUID, task_id: UUID) -> ResultRecord:
        task = self.tasks.get(session, task_id, lock=True)
        if task is None:
            raise rejected("NOT_FOUND")
        conversation = self.conversations.get_conversation(session, task.conversation_id)
        if conversation is None:
            raise rejected("NOT_FOUND")
        self.access.require_member(session, conversation.project_id, actor_id)
        if task.status != "ready":
            raise rejected("TASK_NOT_READY")
        result = self.repository.for_task(session, task_id)
        if result is None:
            self.repository.create(session, new_id(), conversation.project_id, task.conversation_id,
                                   task_id, task.title)
            result = self.repository.for_task(session, task_id)
            assert result is not None
        else:
            result = self.repository.get(session, result.id, lock=True)
            assert result is not None
        result = self._normalized(session, result)
        if result.draft is not None and result.draft.status == "generating":
            return result
        bounds = self.inputs.bounds(session, task.conversation_id)
        if bounds is None:
            raise rejected("TASK_NOT_READY")
        context = self.contexts.snapshot(session, task.conversation_id)
        if result.latest_revision_id is not None:
            previous = self.repository.revision(session, result.latest_revision_id)
            assert previous is not None
            context = ConversationContext(context.resources, (*context.results, ResultInput(
                result.id, previous.id, previous.version, previous.title, previous.conclusion,
            )))
        run = self.requester.request(session, RunRequest(
            result.project_id, task.conversation_id, task_id, RunPurpose.SUMMARY, result.id, actor_id,
        ))
        self.repository.start_draft(session, result, run.run_id, bounds, context)
        updated = self.repository.get(session, result.id)
        assert updated is not None
        self.events.after_commit(session, result_event(updated))
        return updated

    def save(self, session, actor_id: UUID, result_id: UUID, base_version: int, conclusion: str, source_run_id: UUID) -> Revision:
        result = self._require(session, actor_id, result_id, lock=True)
        if base_version != result.latest_version:
            raise rejected("VERSION_CONFLICT", details={"latest_version": result.latest_version,
                                                        "latest_revision_id": str(result.latest_revision_id) if result.latest_revision_id else None})
        conclusion = conclusion.strip()
        if not conclusion or "\x00" in conclusion:
            raise rejected("INVALID_INPUT")
        try:
            conclusion.encode("utf-8")
        except UnicodeEncodeError:
            raise rejected("INVALID_INPUT") from None
        draft = result.draft
        if draft is not None and draft.status == "generating":
            raise rejected("ACTIVE_RUN_EXISTS")
        if draft is not None and draft.status == "ready" and draft.run_id == source_run_id:
            source = Source(result.source_conversation_id, draft.message_from_seq, draft.message_to_seq,
                            tuple(item.revision_id for item in draft.context.resources),
                            tuple(item.result_revision_id for item in draft.context.results), draft.run_id)
        elif result.latest_revision_id is not None:
            revision = self.repository.revision(session, result.latest_revision_id)
            assert revision is not None
            if revision.source.run_id != source_run_id:
                raise rejected("VERSION_CONFLICT")
            source = revision.source
        else:
            raise rejected("VERSION_CONFLICT")
        saved = self.repository.save(session, result, new_id(), base_version, conclusion, source, actor_id)
        if saved is None:
            raise rejected("VERSION_CONFLICT")
        updated = self.repository.get(session, result.id)
        assert updated is not None
        self.events.after_commit(session, result_event(updated))
        return saved
