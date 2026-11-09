from typing import Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.sharing.domain.models import ResultUsage

TransactionT = TypeVar("TransactionT", contravariant=True)


class ResultUsageQuery(Protocol[TransactionT]):
    def list_usages(self, session: TransactionT, project_id: UUID) -> tuple[ResultUsage, ...]: ...
