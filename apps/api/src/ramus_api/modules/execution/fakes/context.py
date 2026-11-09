"""In-memory ContextProvider for tests; transaction arguments are deliberately opaque."""

from collections.abc import Mapping
from uuid import UUID

from ramus_api.modules.execution.domain.models import ConversationContext


class FakeContextProvider:
    def __init__(self, contexts: Mapping[UUID, ConversationContext] | None = None) -> None:
        self._contexts = dict(contexts or {})

    def set_context(self, conversation_id: UUID, context: ConversationContext) -> None:
        """Fixture setup or explicit application of a new pinned version."""
        self._contexts[conversation_id] = context

    def snapshot(self, session: object, conversation_id: UUID) -> ConversationContext:
        return self._contexts.get(conversation_id, ConversationContext())

    def copy_resources(
        self, session: object, source_conversation_id: UUID, target_conversation_id: UUID
    ) -> None:
        source = self.snapshot(session, source_conversation_id)
        target = self.snapshot(session, target_conversation_id)
        self._contexts[target_conversation_id] = ConversationContext(source.resources, target.results)
