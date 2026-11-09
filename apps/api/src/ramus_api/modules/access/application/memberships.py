"""Membership services shared with project use cases through access.public."""

from dataclasses import dataclass
from typing import Generic, TypeVar
from uuid import UUID

from ramus_api.modules.access.application.ports import AccountStore
from ramus_api.modules.access.domain.models import AccountProfile, MembershipRole

T = TypeVar("T")


@dataclass(frozen=True)
class MembershipReader(Generic[T]):
    accounts: AccountStore[T]

    def project_ids(self, transaction: T, account_id: UUID) -> list[UUID]:
        return self.accounts.project_ids(transaction, account_id)

    def participants(self, transaction: T, project_id: UUID) -> list[AccountProfile]:
        return self.accounts.participants(transaction, project_id)


@dataclass(frozen=True)
class MembershipWriter(Generic[T]):
    accounts: AccountStore[T]

    def add_creator(self, transaction: T, account_id: UUID, project_id: UUID) -> None:
        """Grants editing membership within the project's creation transaction."""
        self.accounts.add_membership(transaction, account_id, project_id, MembershipRole.EDITOR)
