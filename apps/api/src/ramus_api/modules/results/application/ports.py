"""Transactional persistence boundary for result use cases."""

from typing import Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.execution.domain.models import ConversationContext
from ramus_api.modules.results.domain.records import ApprovedResult, ResultRecord, Revision, Source

TransactionT = TypeVar("TransactionT", contravariant=True)


class ResultRepository(Protocol[TransactionT]):
    def approved_for_project(self, session: TransactionT, project_id: UUID) -> tuple[ApprovedResult, ...]: ...
    def get(self, session: TransactionT, result_id: UUID, *, lock: bool = False) -> ResultRecord | None: ...
    def for_task(self, session: TransactionT, task_id: UUID) -> ResultRecord | None: ...
    def create(
        self, session: TransactionT, result_id: UUID, project_id: UUID, conversation_id: UUID,
        task_id: UUID, title: str,
    ) -> None: ...
    def revision(self, session: TransactionT, revision_id: UUID) -> Revision | None: ...
    def start_draft(
        self, session: TransactionT, result: ResultRecord, run_id: UUID,
        bounds: tuple[int, int], context: ConversationContext,
    ) -> None: ...
    def finish_draft(
        self, session: TransactionT, result_id: UUID, run_id: UUID,
        conclusion: str | None, error_code: str | None,
    ) -> bool: ...
    def save(
        self, session: TransactionT, result: ResultRecord, revision_id: UUID,
        base_version: int, conclusion: str, source: Source, actor_id: UUID,
    ) -> Revision | None: ...
