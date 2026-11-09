"""Ports the resources use cases depend on. The caller owns the transaction (``session``)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.resources.domain.models import ResourceKind
from ramus_api.modules.resources.domain.rules import RevisionContent, RevisionRef

TransactionT = TypeVar("TransactionT", contravariant=True)


@dataclass(frozen=True)
class RevisionRecord:
    id: UUID
    resource_id: UUID
    number: int
    content: RevisionContent
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True)
class RevisionEntry:
    id: UUID
    number: int
    name: str
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True)
class ResourceRecord:
    id: UUID
    project_id: UUID
    kind: ResourceKind
    latest: RevisionRecord


@dataclass(frozen=True)
class ResourceHistory:
    resource: ResourceRecord
    revisions: tuple[RevisionEntry, ...]  # oldest first


@dataclass(frozen=True)
class AppliedRecord:
    resource_id: UUID
    revision_id: UUID
    number: int
    name: str
    kind: ResourceKind


@dataclass(frozen=True)
class NewResource:
    resource_id: UUID
    revision_id: UUID
    project_id: UUID
    kind: ResourceKind
    content: RevisionContent
    content_hash: str
    created_by: UUID


class ResourceRepository(Protocol[TransactionT]):
    def add(self, session: TransactionT, resource: NewResource) -> None: ...

    def history(self, session: TransactionT, resource_id: UUID) -> ResourceHistory | None: ...

    def search(self, session: TransactionT, project_id: UUID, query: str) -> Sequence[ResourceRecord]:
        """Resources whose latest name or description contains ``query`` (case-insensitive), by name."""
        ...

    def applied(self, session: TransactionT, conversation_id: UUID) -> Sequence[AppliedRecord]: ...

    def revision_refs(self, session: TransactionT, revision_ids: Sequence[UUID]) -> Sequence[RevisionRef]: ...

    def replace_applied(
        self, session: TransactionT, conversation_id: UUID, revisions: Sequence[RevisionRef], applied_by: UUID
    ) -> None: ...


# --- Provided by track A (access / conversations). Not in contracts.md yet; see PR description. ---


class ProjectMembership(Protocol[TransactionT]):
    def is_member(self, session: TransactionT, account_id: UUID, project_id: UUID) -> bool: ...


class ConversationDirectory(Protocol[TransactionT]):
    def project_of(self, session: TransactionT, conversation_id: UUID) -> UUID | None: ...
