"""B1 use cases: register a shared skill/material (v1), search, and pin versions on a conversation.

Each function runs inside the caller's transaction and returns the events to publish after commit.
Access rules (contracts.md §1): non-members and unknown targets both get ``NOT_FOUND``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from ramus_api.modules.realtime.domain.events import EventName, ProjectEvent
from ramus_api.modules.resources.application.ports import (
    AppliedRecord,
    ConversationDirectory,
    NewResource,
    ProjectMembership,
    ResourceHistory,
    ResourceRecord,
    ResourceRepository,
)
from ramus_api.modules.resources.domain.models import ResourceKind
from ramus_api.modules.resources.domain.rules import (
    NOT_FOUND,
    ResourceRuleError,
    check_applied_selection,
    content_hash,
    normalize_content,
)

TransactionT = TypeVar("TransactionT")
T = TypeVar("T")


@dataclass(frozen=True)
class Outcome(Generic[T]):
    value: T
    events: tuple[ProjectEvent, ...] = ()


@dataclass(frozen=True)
class ResourceDraft:
    kind: ResourceKind
    name: str
    description: str
    instructions: str | None
    content: str | None
    file_name: str | None


@dataclass(frozen=True)
class SearchHit:
    resource: ResourceRecord
    applied: AppliedRecord | None


@dataclass(frozen=True)
class ResourceUseCases(Generic[TransactionT]):
    repository: ResourceRepository[TransactionT]
    membership: ProjectMembership[TransactionT]
    conversations: ConversationDirectory[TransactionT]
    new_id: Callable[[], UUID]
    now: Callable[[], datetime]

    # --- guards -------------------------------------------------------------------------------

    def _require_member(self, session: TransactionT, actor_id: UUID, project_id: UUID) -> None:
        if not self.membership.is_member(session, actor_id, project_id):
            raise ResourceRuleError(NOT_FOUND)

    def _conversation_project(self, session: TransactionT, actor_id: UUID, conversation_id: UUID) -> UUID:
        project_id = self.conversations.project_of(session, conversation_id)
        if project_id is None:
            raise ResourceRuleError(NOT_FOUND)
        self._require_member(session, actor_id, project_id)
        return project_id

    # --- commands and queries -----------------------------------------------------------------

    def create(
        self, session: TransactionT, actor_id: UUID, project_id: UUID, draft: ResourceDraft
    ) -> Outcome[ResourceHistory]:
        """Registers a resource with its first revision (v1)."""
        self._require_member(session, actor_id, project_id)
        content = normalize_content(
            draft.kind,
            name=draft.name,
            description=draft.description,
            instructions=draft.instructions,
            content=draft.content,
            file_name=draft.file_name,
        )
        resource_id, revision_id = self.new_id(), self.new_id()
        self.repository.add(
            session,
            NewResource(
                resource_id=resource_id,
                revision_id=revision_id,
                project_id=project_id,
                kind=draft.kind,
                content=content,
                content_hash=content_hash(content),
                created_by=actor_id,
            ),
        )
        history = self.repository.history(session, resource_id)
        if history is None:  # pragma: no cover - the row was just written in this transaction
            raise RuntimeError("created resource is not readable")
        event = ProjectEvent(
            project_id=project_id,
            name=EventName.RESOURCE_UPDATED,
            occurred_at=self.now(),
            data={
                "project_id": str(project_id),
                "resource_id": str(resource_id),
                "latest_revision_id": str(revision_id),
                "latest_number": history.resource.latest.number,
            },
        )
        return Outcome(history, (event,))

    def search(
        self,
        session: TransactionT,
        actor_id: UUID,
        project_id: UUID,
        query: str,
        conversation_id: UUID | None,
    ) -> tuple[SearchHit, ...]:
        """Matches name/description of the latest revision. With a conversation, shows its pinned version."""
        self._require_member(session, actor_id, project_id)
        applied: dict[UUID, AppliedRecord] = {}
        if conversation_id is not None:
            if self.conversations.project_of(session, conversation_id) != project_id:
                raise ResourceRuleError(NOT_FOUND)
            applied = {item.resource_id: item for item in self.repository.applied(session, conversation_id)}
        found = self.repository.search(session, project_id, query.strip())
        return tuple(SearchHit(resource, applied.get(resource.id)) for resource in found)

    def list_applied(
        self, session: TransactionT, actor_id: UUID, conversation_id: UUID
    ) -> tuple[AppliedRecord, ...]:
        self._conversation_project(session, actor_id, conversation_id)
        return tuple(self.repository.applied(session, conversation_id))

    def replace_applied(
        self, session: TransactionT, actor_id: UUID, conversation_id: UUID, revision_ids: Sequence[UUID]
    ) -> Outcome[tuple[AppliedRecord, ...]]:
        """Replaces the whole pinned set. Exact revision ids only; never resolves to "latest"."""
        project_id = self._conversation_project(session, actor_id, conversation_id)
        refs = check_applied_selection(
            revision_ids,
            self.repository.revision_refs(session, list(dict.fromkeys(revision_ids))),
            project_id,
        )
        before = tuple(self.repository.applied(session, conversation_id))
        if {item.revision_id for item in before} == {ref.revision_id for ref in refs}:
            return Outcome(before)
        self.repository.replace_applied(session, conversation_id, refs, actor_id)
        event = ProjectEvent(
            project_id=project_id,
            name=EventName.CONVERSATION_RESOURCES_UPDATED,
            occurred_at=self.now(),
            data={"conversation_id": str(conversation_id)},
        )
        return Outcome(tuple(self.repository.applied(session, conversation_id)), (event,))
