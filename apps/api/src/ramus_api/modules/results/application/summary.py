"""Summary purpose handler; model calls and run transitions remain execution's responsibility."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from ramus_api.modules.conversations.application.ports import CommittedEvents
from ramus_api.modules.conversations.application.summary_inputs import SummaryInputReader
from ramus_api.modules.execution.application.output_schema import SummaryOutput
from ramus_api.modules.execution.domain.models import (
    ConversationContext,
    LlmFailure,
    LlmRequest,
    RunError,
    RunView,
)
from ramus_api.modules.results.application.events import result_event
from ramus_api.modules.results.application.ports import ResultRepository
from ramus_api.modules.results.domain.summary import build_summary_request


@dataclass(frozen=True)
class SummaryPurposeHandler:
    repository: ResultRepository[Any]
    inputs: SummaryInputReader[Any]
    events: CommittedEvents[Any]
    purpose = "summary"

    def build_request(self, session, run: RunView, context: ConversationContext) -> LlmRequest:
        result = self.repository.get(session, run.target_id)
        if (result is None or result.draft is None or result.draft.run_id != run.id
                or result.project_id != run.project_id or result.source_conversation_id != run.conversation_id
                or result.source_task_id != run.task_id):
            raise ValueError("Summary run does not match its result draft")
        draft = result.draft
        previous = next((item for item in result.revisions if item.version == draft.base_version), None)
        after_seq = previous.source.message_to_seq if previous else 0
        messages = self.inputs.read(session, run.conversation_id, after_seq, draft.message_to_seq)
        return build_summary_request(run, draft.context, messages, previous,
                                     (draft.message_from_seq, draft.message_to_seq))

    def complete(self, session, run: RunView, output: Mapping[str, Any]) -> None:
        try:
            parsed = SummaryOutput.model_validate(dict(output))
        except (ValidationError, ValueError, TypeError):
            raise LlmFailure("LLM_OUTPUT_INVALID") from None
        self._finish(session, run, parsed.conclusion, None)

    def fail(self, session, run: RunView, error: RunError) -> None:
        self._finish(session, run, None, error.code)

    def _finish(self, session, run, conclusion, error_code) -> None:
        if self.repository.finish_draft(session, run.target_id, run.id, conclusion, error_code):
            result = self.repository.get(session, run.target_id)
            assert result is not None
            self.events.after_commit(session, result_event(result))
