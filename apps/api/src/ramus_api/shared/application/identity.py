"""Session authentication port used at HTTP boundaries."""

from typing import Protocol

from ramus_api.shared.domain.identity import AuthenticatedAccount


class SessionAuthenticator(Protocol):
    def authenticate(self, token: str | None) -> AuthenticatedAccount | None: ...

    def logout(self, token: str | None) -> None: ...
