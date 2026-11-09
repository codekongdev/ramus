"""Read-only relationship map assembled from module-owned projections."""

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.access.public import MembershipReader, TransactionFactory
from ramus_api.modules.conversations.public import ConversationRecord
from ramus_api.modules.projects.application.queries import ProjectNotFound
from ramus_api.modules.sharing.public import ResultUsage

T = TypeVar("T")


class Conversations(Protocol[T]):
    def list_conversations(self, session: T, project_id: UUID) -> tuple[ConversationRecord, ...]: ...


class TaskStatuses(Protocol[T]):
    def by_ids(self, session: T, task_ids: tuple[UUID, ...]) -> dict[UUID, str]: ...


class ResultUsages(Protocol[T]):
    def list_usages(self, session: T, project_id: UUID) -> tuple[ResultUsage, ...]: ...


@dataclass(frozen=True)
class Node:
    conversation_id: UUID
    title: str
    parent_id: UUID | None
    task_status: str | None


@dataclass(frozen=True)
class Edge:
    kind: str
    source: UUID
    to: UUID


@dataclass(frozen=True)
class Graph:
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]


@dataclass(frozen=True)
class ProjectGraphQuery(Generic[T]):
    transactions: TransactionFactory[T]
    memberships: MembershipReader[T]
    conversations: Conversations[T]
    statuses: TaskStatuses[T]
    usages: ResultUsages[T]

    def get(self, account_id: UUID, project_id: UUID) -> Graph:
        with self.transactions() as session:
            if project_id not in self.memberships.project_ids(session, account_id):
                raise ProjectNotFound()
            conversations = self.conversations.list_conversations(session, project_id)
            statuses = self.statuses.by_ids(session, tuple(c.task_id for c in conversations if c.task_id))
            ids = {c.id for c in conversations}
            nodes = tuple(Node(c.id, c.title, c.parent_id, statuses.get(c.task_id)) for c in conversations)
            branches = tuple(Edge("branch", c.parent_id, c.id) for c in conversations if c.parent_id in ids)
            usages = self.usages.list_usages(session, project_id)
            # Different pinned results can have the same endpoints; the map needs only one line.
            pairs = dict.fromkeys((u.source_conversation_id, u.target_conversation_id) for u in usages
                                  if u.source_conversation_id in ids and u.target_conversation_id in ids)
            return Graph(nodes, branches + tuple(Edge("uses_result", source, target) for source, target in pairs))
