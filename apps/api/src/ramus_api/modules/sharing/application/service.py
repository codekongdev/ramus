"""Send saved conclusions atomically; callers own transactions and idempotency receipts."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ramus_api.modules.access.application.ports import ProjectAccess
from ramus_api.modules.conversations.application.ports import CommittedEvents
from ramus_api.modules.realtime.domain.events import EventName, ProjectEvent
from ramus_api.modules.sharing.application.errors import invalid_target, not_found
from ramus_api.modules.sharing.application.ports import ConversationReader, ResultReader, SharingRepository
from ramus_api.modules.sharing.domain.records import ReceivedInput, SharedTarget, ShareOutcome
from ramus_api.shared.domain.primitives import utc_now


@dataclass(frozen=True)
class SharingService:
    repository: SharingRepository[Any]
    results: ResultReader[Any]
    conversations: ConversationReader[Any]
    access: ProjectAccess[Any]
    events: CommittedEvents[Any]

    def require_send_access(self, session, actor_id: UUID, revision_id: UUID, targets: tuple[UUID, ...], *, lock=False):
        revision = self.results.revision(session, revision_id)
        if revision is None:
            raise not_found()
        result = self.results.get(session, revision.result_id, lock=lock)
        if result is None:
            raise not_found()
        self.access.require_member(session, result.project_id, actor_id)
        if not targets or len(set(targets)) != len(targets) or result.source_conversation_id in targets:
            raise invalid_target()
        # Validate the complete batch before writing any history or input snapshot.
        for target_id in targets:
            target = self.conversations.get_conversation(session, target_id)
            if target is None:
                raise not_found()
            self.access.require_member(session, target.project_id, actor_id)
            if target.project_id != result.project_id:
                raise invalid_target()
        return result, revision

    def send(self, session, actor_id: UUID, revision_id: UUID, targets: tuple[UUID, ...]) -> tuple[SharedTarget, ...]:
        # The result lock serializes sends of all versions, including concurrent initial links.
        # Approval takes the same lock; no update can overwrite a newer pinned version.
        result, revision = self.require_send_access(session, actor_id, revision_id, targets, lock=True)
        outcomes = []
        for target_id in targets:
            outcome = self.repository.pin(session, target_id, revision, actor_id)
            outcomes.append(SharedTarget(target_id, outcome))
            if outcome in (ShareOutcome.LINKED, ShareOutcome.REPLACED):
                self.events.after_commit(session, ProjectEvent(
                    result.project_id, EventName.CONVERSATION_INPUTS_UPDATED, utc_now(),
                    {"conversation_id": target_id},
                ))
        return tuple(outcomes)

    def received(self, session, actor_id: UUID, conversation_id: UUID) -> tuple[ReceivedInput, ...]:
        conversation = self.conversations.get_conversation(session, conversation_id)
        if conversation is None:
            raise not_found()
        self.access.require_member(session, conversation.project_id, actor_id)
        items = self.repository.list_inputs(session, conversation_id)
        versions = self.results.latest_versions(session, tuple(item.result_id for item in items))
        return tuple(ReceivedInput(item, versions[item.result_id]) for item in items)
