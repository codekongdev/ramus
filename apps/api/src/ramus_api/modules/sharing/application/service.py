"""Send saved conclusions atomically; callers own transactions and idempotency receipts."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ramus_api.modules.access.application.ports import ProjectAccess
from ramus_api.modules.access.public import MembershipReader
from ramus_api.modules.conversations.application.ports import CommittedEvents
from ramus_api.modules.realtime.domain.events import EventName, ProjectEvent
from ramus_api.modules.results.public import ApprovedConclusion
from ramus_api.modules.sharing.application.errors import invalid_target, not_found
from ramus_api.modules.sharing.application.followups import Inputs
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
    memberships: MembershipReader[Any]
    snapshots: Inputs

    def require_send_access(self, session, actor_id: UUID, revision_id: UUID, targets: tuple[UUID, ...], *, lock=False):
        revision = self.results.revision(session, revision_id)
        if revision is None:
            raise not_found()
        result = self.results.get(session, revision.result_id, lock=lock)
        if result is None:
            raise not_found()
        projects = set(self.memberships.project_ids(session, actor_id))
        received = []
        for snapshot in self.snapshots.received(session, revision_id):
            conversation = self.conversations.get_conversation(session, snapshot.conversation_id)
            if conversation is not None and conversation.project_id in projects:
                received.append((conversation.project_id, snapshot))
        # Establish access before reporting target-validation errors; otherwise an owner
        # of unrelated projects could distinguish an inaccessible revision from a missing one.
        if result.project_id not in projects and not received:
            raise not_found()
        if not targets or len(set(targets)) != len(targets) or result.source_conversation_id in targets:
            if result.project_id not in projects:
                raise not_found()
            raise invalid_target()
        # Validate every destination and its current membership before writing any snapshot.
        target_projects = set()
        for target_id in targets:
            target = self.conversations.get_conversation(session, target_id)
            if target is None:
                raise not_found()
            self.access.require_member(session, target.project_id, actor_id)
            target_projects.add(target.project_id)
        if len(target_projects) != 1:
            raise invalid_target()
        target_project = next(iter(target_projects))
        if target_project == result.project_id:
            self.access.require_member(session, result.project_id, actor_id)
            return result, revision, target_project

        # B7 recipients may forward only the exact input already received within the
        # destination project. This never grants access to newer source revisions or
        # enables B6 sends into an unrelated project, even for a source-project member.
        for received_project, snapshot in received:
            if received_project == target_project:
                received_revision = ApprovedConclusion(
                    snapshot.result_revision_id, snapshot.result_id, result.project_id,
                    snapshot.version, snapshot.version, snapshot.title, snapshot.conclusion, snapshot.source,
                )
                return result, received_revision, target_project
        if result.project_id in projects:
            raise invalid_target()
        raise not_found()

    def send(self, session, actor_id: UUID, revision_id: UUID, targets: tuple[UUID, ...]) -> tuple[SharedTarget, ...]:
        # The result lock serializes sends of all versions, including concurrent initial links.
        # Approval takes the same lock; no update can overwrite a newer pinned version.
        _result, revision, target_project = self.require_send_access(session, actor_id, revision_id, targets, lock=True)
        outcomes = []
        for target_id in targets:
            outcome = self.repository.pin(session, target_id, revision, actor_id)
            outcomes.append(SharedTarget(target_id, outcome))
            if outcome in (ShareOutcome.LINKED, ShareOutcome.REPLACED):
                self.events.after_commit(session, ProjectEvent(
                    target_project, EventName.CONVERSATION_INPUTS_UPDATED, utc_now(),
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
