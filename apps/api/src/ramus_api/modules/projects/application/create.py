"""Create a project and its creator's access in one idempotent transaction."""

from dataclasses import dataclass
from typing import Generic, TypeVar
from uuid import UUID

from ramus_api.modules.access.public import MembershipWriter
from ramus_api.modules.projects.application.queries import ProjectRepository
from ramus_api.modules.projects.domain.project import validate_project_name
from ramus_api.shared.application.idempotency import IdempotentExecutor, JsonObject

T = TypeVar("T")


@dataclass(frozen=True)
class CreateProject(Generic[T]):
    idempotency: IdempotentExecutor[T]
    projects: ProjectRepository[T]
    memberships: MembershipWriter[T]

    def execute(self, account_id: UUID, name: str, key: str) -> JsonObject:
        validate_project_name(name)

        def operation(transaction: T) -> JsonObject:
            project = self.projects.create(transaction, name)
            self.memberships.add_creator(transaction, account_id, project.id)
            return {"id": str(project.id), "name": project.name, "is_shared_sample": False}

        return self.idempotency.execute_once(
            str(account_id), "projects.create", key, {"name": name}, operation
        )
