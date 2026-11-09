"""Recording writer: no database transaction/authorization/sequence allocation is simulated."""

from uuid import UUID, uuid5

from ramus_api.modules.conversations.domain.models import NewChildConversation, NewMessage

WRITER_NAMESPACE = UUID("f165b3a4-fdee-536e-a3c0-31cae098143c")


class FakeConversationWriter:
    def __init__(self) -> None:
        self._messages: list[tuple[UUID, NewMessage]] = []
        self._children: list[tuple[UUID, NewChildConversation]] = []

    @property
    def messages(self) -> tuple[tuple[UUID, NewMessage], ...]:
        return tuple(self._messages)

    @property
    def children(self) -> tuple[tuple[UUID, NewChildConversation], ...]:
        return tuple(self._children)

    def append_message(self, session: object, message: NewMessage) -> UUID:
        identifier = uuid5(WRITER_NAMESPACE, f"message:{message.run_id}:{len(self._messages)}")
        self._messages.append((identifier, message))
        return identifier

    def create_child(self, session: object, conversation: NewChildConversation) -> UUID:
        identifier = uuid5(WRITER_NAMESPACE, f"child:{conversation.task_id}")
        self._children.append((identifier, conversation))
        return identifier
