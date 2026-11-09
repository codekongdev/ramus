"""Project reads authorized by the caller's membership."""

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.access.public import AccountProfile, MembershipReader, TransactionFactory
from ramus_api.modules.projects.domain.project import ProjectInfo

T = TypeVar("T")


class ProjectNotFound(Exception):
    """The project is absent or inaccessible to this account."""


class ProjectRepository(Protocol[T]):
    def list_by_ids(self, transaction: T, ids: list[UUID]) -> list[ProjectInfo]: ...


@dataclass(frozen=True)
class ProjectQueries(Generic[T]):
    transactions: TransactionFactory[T]
    memberships: MembershipReader[T]
    projects: ProjectRepository[T]

    def list_projects(self, account_id: UUID) -> list[ProjectInfo]:
        with self.transactions() as transaction:
            ids = self.memberships.project_ids(transaction, account_id)
            return self.projects.list_by_ids(transaction, ids)

    def participants(self, account_id: UUID, project_id: UUID) -> list[AccountProfile]:
        with self.transactions() as transaction:
            if project_id not in self.memberships.project_ids(transaction, account_id):
                raise ProjectNotFound()
            return self.memberships.participants(transaction, project_id)
