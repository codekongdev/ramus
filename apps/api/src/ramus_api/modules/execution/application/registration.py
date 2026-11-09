"""``RunRequester`` implementation: registers a pending run inside the caller's transaction."""

from typing import Any

from ramus_api.modules.execution.application.errors import business_error
from ramus_api.modules.execution.application.events import RunAnnouncer
from ramus_api.modules.execution.application.ports import AiConnectionQuery
from ramus_api.modules.execution.application.runtime_ports import RunStore
from ramus_api.modules.execution.domain import errors as codes
from ramus_api.modules.execution.domain.errors import ActiveRunConflict
from ramus_api.modules.execution.domain.models import RunRef, RunRequest
from ramus_api.modules.execution.domain.snapshot import EMPTY_SNAPSHOT
from ramus_api.shared.domain.primitives import new_id


class RunRegistrationService:
    """Never commits. The partial unique indexes, not a prior SELECT, decide ``ACTIVE_RUN_EXISTS``."""

    def __init__(
        self, store: RunStore[Any], connections: AiConnectionQuery[Any], announcer: RunAnnouncer
    ) -> None:
        self._store = store
        self._connections = connections
        self._announcer = announcer

    def request(self, session: Any, request: RunRequest) -> RunRef:
        if not self._connections.is_connected(session, request.requested_by):
            raise business_error(codes.AI_CONNECTION_REQUIRED)
        try:
            # ON-AC-08: a run always spends the requester's own key.
            state = self._store.insert(session, new_id(), request, request.requested_by, EMPTY_SNAPSHOT)
        except ActiveRunConflict:
            raise business_error(codes.ACTIVE_RUN_EXISTS) from None
        self._announcer.changed(session, state)
        self._announcer.queued(session)
        return RunRef(state.id, state.status)
