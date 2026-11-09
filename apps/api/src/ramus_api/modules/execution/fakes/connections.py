"""In-memory AiConnectionQuery for tests until access (A3) provides the real one."""

from collections.abc import Iterable
from uuid import UUID


class FakeAiConnectionQuery:
    def __init__(self, connected_accounts: Iterable[UUID] = ()) -> None:
        self._connected = frozenset(connected_accounts)

    def set_connected(self, account_id: UUID, connected: bool) -> None:
        self._connected = self._connected | {account_id} if connected else self._connected - {account_id}

    def is_connected(self, session: object, account_id: UUID) -> bool:
        return account_id in self._connected
