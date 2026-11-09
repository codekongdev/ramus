from collections.abc import Iterable, Mapping
from uuid import UUID

from ramus_api.modules.sharing.domain.models import ResultUsage


class FakeResultUsageQuery:
    def __init__(self, usages: Mapping[UUID, Iterable[ResultUsage]] | None = None) -> None:
        self._usages = {project_id: tuple(items) for project_id, items in (usages or {}).items()}

    def list_usages(self, session: object, project_id: UUID) -> tuple[ResultUsage, ...]:
        return self._usages.get(project_id, ())
