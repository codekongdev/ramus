"""SQL wiring for conversations. Cross-module services arrive through public ports."""

from sqlalchemy.orm import Session

from ramus_api.container import AppContainer
from ramus_api.modules.conversations.application.ports import (
    CommittedEvents as CommittedEventsPort,
)
from ramus_api.modules.conversations.application.ports import ProjectAccess, RunReader
from ramus_api.modules.conversations.application.service import ConversationService
from ramus_api.modules.conversations.infrastructure.repository import SqlConversationRepository
from ramus_api.modules.execution.application.ports import RunRequester
from ramus_api.modules.realtime.application.schemas import validate_event
from ramus_api.modules.realtime.domain.events import ProjectEvent


class CommittedEvents:
    def __init__(self, container: AppContainer) -> None:
        self._hooks = container.event_hooks
        self._relay = container.event_relay

    def after_commit(self, session: Session, event: ProjectEvent) -> None:
        validated = validate_event(event)
        self._hooks.after_commit(session, lambda: self._relay.enqueue(validated))


def build_conversation_service(
    container: AppContainer,
    access: ProjectAccess[Session],
    requester: RunRequester[Session],
    runs: RunReader[Session],
    events: CommittedEventsPort[Session],
) -> ConversationService[Session]:
    return ConversationService(
        container.database.transaction,
        SqlConversationRepository(),
        access,
        container.idempotency,
        requester,
        runs,
        events,
    )
