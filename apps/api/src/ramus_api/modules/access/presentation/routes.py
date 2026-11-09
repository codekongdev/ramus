"""Access endpoints: email-code login, session, and the account's AI connection.

Login, logout, and ``GET /api/me`` are implemented (P0-A4). The AI connection endpoints stay stubs
until task A3.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from sqlalchemy.orm import Session

from ramus_api.container import AppContainer
from ramus_api.modules.access.application.ports import SharedProjectProvider
from ramus_api.modules.access.composition import AccessServices, build_access_services
from ramus_api.modules.access.domain.models import MeProfile
from ramus_api.modules.access.presentation.cookies import (
    clear_session_cookie,
    read_session_token,
    set_session_cookie,
)
from ramus_api.modules.access.presentation.current_account import AuthenticatedAccount, require_account
from ramus_api.modules.access.presentation.dto import (
    Account,
    AiConnectionConnected,
    AiConnectionDisconnected,
    AiConnectionState,
    ConnectAiRequest,
    Me,
    RequestEmailCodeRequest,
    RequestEmailCodeResponse,
    VerifyEmailCodeRequest,
)
from ramus_api.modules.access.presentation.errors import access_errors
from ramus_api.shared.presentation.error_messages import not_implemented
from ramus_api.shared.presentation.idempotency import IdempotencyKey
from ramus_api.shared.presentation.schemas import EmptyRequest, EmptyResponse


def to_me(profile: MeProfile) -> Me:
    account = profile.account
    return Me(
        account=Account(id=account.id, email=account.email, display_name=account.display_name),
        default_project_id=profile.default_project_id,
        ai_connection=AiConnectionState(status=profile.ai_connection.value),
    )


def register(app: FastAPI, container: AppContainer, *, shared_project: SharedProjectProvider[Session]) -> None:
    services = build_access_services(container, shared_project)
    router = APIRouter(prefix="/api", tags=["access"])
    _add_login_routes(router, container, services)
    _add_ai_connection_stubs(router)
    app.include_router(router)


def _add_login_routes(router: APIRouter, container: AppContainer, services: AccessServices) -> None:
    secure = container.settings.cookie_secure
    CurrentAccount = Annotated[AuthenticatedAccount, Depends(require_account(container))]

    @router.post(
        "/auth/email-code",
        status_code=202,
        response_model=RequestEmailCodeResponse,
        operation_id="requestEmailCode",
    )
    async def request_email_code(body: RequestEmailCodeRequest, idempotency_key: IdempotencyKey):
        # The same response whether or not an account exists for the address.
        with access_errors():
            available_at = await services.request_email_code(body.email, idempotency_key)
        return RequestEmailCodeResponse(resend_available_at=available_at)

    @router.post("/auth/verify", response_model=Me, operation_id="verifyEmailCode")
    def verify_email_code(body: VerifyEmailCodeRequest, idempotency_key: IdempotencyKey, response: Response):
        with access_errors():
            issued = services.verify_email_code(body.email, body.code, idempotency_key)
        set_session_cookie(response, issued.token, secure=secure)
        return to_me(issued.me)

    @router.post("/auth/logout", response_model=EmptyResponse, operation_id="logout")
    def logout(body: EmptyRequest, idempotency_key: IdempotencyKey, request: Request, response: Response):
        # No receipt: revoking an already revoked (or absent) session and clearing the cookie again
        # has the same effect, so the request is idempotent by itself. The key is still required by
        # the shared change-request rule (docs/contracts.md 1).
        services.authenticator.logout(read_session_token(request))
        clear_session_cookie(response, secure=secure)
        return EmptyResponse()

    @router.get("/me", response_model=Me, operation_id="getMe")
    def get_me(account: CurrentAccount):
        return to_me(services.profiles.get_me(account.account_id))


def _add_ai_connection_stubs(router: APIRouter) -> None:
    @router.get("/me/ai-connection", response_model=AiConnectionState, operation_id="getAiConnection")
    def get_ai_connection():
        raise not_implemented()

    @router.put("/me/ai-connection", response_model=AiConnectionConnected, operation_id="connectAi")
    def connect_ai(body: ConnectAiRequest, idempotency_key: IdempotencyKey):
        raise not_implemented()

    @router.delete("/me/ai-connection", response_model=AiConnectionDisconnected, operation_id="disconnectAi")
    def disconnect_ai(idempotency_key: IdempotencyKey):
        raise not_implemented()
