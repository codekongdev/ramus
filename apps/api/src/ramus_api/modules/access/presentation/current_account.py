"""Current-account dependency: the public way for other modules to require a logged-in account.

Usage inside another module's ``register(app, container)``::

    from typing import Annotated
    from fastapi import Depends
    from ramus_api.modules.access.presentation.current_account import AuthenticatedAccount, require_account

    def register(app: FastAPI, container: AppContainer) -> None:
        CurrentAccount = Annotated[AuthenticatedAccount, Depends(require_account(container))]

        @router.get("/projects")
        def list_projects(account: CurrentAccount): ...

A request without a valid session (no cookie, unknown, revoked, or expired) gets 401 ``UNAUTHORIZED``.
The cookie is read from ``request.cookies``, so no parameter is added to the OpenAPI document.
"""

from collections.abc import Callable

from fastapi import Request

from ramus_api.container import AppContainer
from ramus_api.modules.access.domain.models import AuthenticatedAccount
from ramus_api.modules.access.presentation.cookies import read_session_token
from ramus_api.modules.access.presentation.errors import unauthorized

__all__ = ["AuthenticatedAccount", "require_account"]


def require_account(container: AppContainer) -> Callable[[Request], AuthenticatedAccount]:
    """Returns a FastAPI dependency resolving the session cookie to an ``AuthenticatedAccount``."""
    authenticator = container.authenticator

    def current_account(request: Request) -> AuthenticatedAccount:
        account = authenticator.authenticate(read_session_token(request))
        if account is None:
            raise unauthorized()
        return account

    return current_account
