"""Access endpoints: email-code login, session, and the account's private AI connection."""

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from sqlalchemy.orm import Session

from ramus_api.container import AppContainer
from ramus_api.modules.access.application.errors import AUTH_METHOD_DISABLED, AccessRejected
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
    PasswordConfigured,
    PasswordLoginRequest,
    PasswordState,
    RegisterAccountRequest,
    RequestEmailCodeRequest,
    RequestEmailCodeResponse,
    SetInitialPasswordRequest,
    VerifyEmailCodeRequest,
)
from ramus_api.modules.access.presentation.errors import access_errors, unauthorized
from ramus_api.shared.presentation.idempotency import IdempotencyKey
from ramus_api.shared.presentation.schemas import EmptyRequest, EmptyResponse


def to_me(profile: MeProfile) -> Me:
    account = profile.account
    return Me(
        account=Account(id=account.id, email=account.email, display_name=account.display_name),
        default_project_id=profile.default_project_id,
        ai_connection=AiConnectionState(status=profile.ai_connection.value),
    )


def register(
    app: FastAPI, container: AppContainer, *, shared_project: SharedProjectProvider[Session]
) -> None:
    services = build_access_services(container, shared_project)
    router = APIRouter(prefix="/api", tags=["access"])
    _add_login_routes(router, container, services)
    _add_password_setup_routes(router, container, services)
    _add_ai_connection_routes(router, container, services)
    app.include_router(router)


def _add_login_routes(router: APIRouter, container: AppContainer, services: AccessServices) -> None:
    secure = container.settings.cookie_secure

    @router.post("/auth/register", response_model=Me, operation_id="registerAccount")
    def register_account(
        body: RegisterAccountRequest, idempotency_key: IdempotencyKey, response: Response, request: Request
    ):
        with access_errors():
            issued = services.passwords.register(
                body.email, body.password.get_secret_value(), body.display_name, idempotency_key,
                request.client.host if request.client else "unknown",
            )
        set_session_cookie(response, issued.token, expires_at=issued.expires_at, secure=secure)
        return to_me(issued.me)

    @router.post("/auth/login", response_model=Me, operation_id="loginWithPassword")
    def login_with_password(
        body: PasswordLoginRequest, idempotency_key: IdempotencyKey, response: Response, request: Request
    ):
        with access_errors():
            issued = services.passwords.login(
                body.email, body.password.get_secret_value(), idempotency_key,
                request.client.host if request.client else "unknown",
            )
        set_session_cookie(response, issued.token, expires_at=issued.expires_at, secure=secure)
        return to_me(issued.me)

    @router.post(
        "/auth/email-code",
        status_code=202,
        response_model=RequestEmailCodeResponse,
        operation_id="requestEmailCode",
    )
    async def request_email_code(
        body: RequestEmailCodeRequest, idempotency_key: IdempotencyKey, request: Request
    ):
        # The same response whether or not an account exists for the address.
        with access_errors():
            if not container.settings.email_code_auth_enabled:
                raise AccessRejected(AUTH_METHOD_DISABLED)
            available_at = await services.request_email_code(
                body.email, idempotency_key, request.client.host if request.client else "unknown"
            )
        return RequestEmailCodeResponse(resend_available_at=available_at)

    @router.post("/auth/verify", response_model=Me, operation_id="verifyEmailCode")
    def verify_email_code(
        body: VerifyEmailCodeRequest, idempotency_key: IdempotencyKey, response: Response, request: Request
    ):
        with access_errors():
            if not container.settings.email_code_auth_enabled:
                raise AccessRejected(AUTH_METHOD_DISABLED)
            issued = services.verify_email_code(
                body.email, body.code, idempotency_key, request.client.host if request.client else "unknown"
            )
        set_session_cookie(response, issued.token, expires_at=issued.expires_at, secure=secure)
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
    def get_me(request: Request):
        profile = services.profiles.authenticated_me(read_session_token(request))
        if profile is None:
            raise unauthorized()
        return to_me(profile)


def _add_ai_connection_routes(router: APIRouter, container: AppContainer, services: AccessServices) -> None:
    CurrentAccount = Annotated[AuthenticatedAccount, Depends(require_account(container))]

    @router.get("/me/ai-connection", response_model=AiConnectionState, operation_id="getAiConnection")
    def get_ai_connection(account: CurrentAccount):
        return AiConnectionState(status=services.ai_connections.status(account.account_id).value)

    @router.put("/me/ai-connection", response_model=AiConnectionConnected, operation_id="connectAi")
    async def connect_ai(body: ConnectAiRequest, idempotency_key: IdempotencyKey, account: CurrentAccount):
        with access_errors():
            await services.ai_connections.connect(account.account_id, body.api_key, idempotency_key)
        return AiConnectionConnected(status="connected")

    @router.delete("/me/ai-connection", response_model=AiConnectionDisconnected, operation_id="disconnectAi")
    def disconnect_ai(idempotency_key: IdempotencyKey, account: CurrentAccount):
        services.ai_connections.disconnect(account.account_id, idempotency_key)
        return AiConnectionDisconnected(status="none")


def _add_password_setup_routes(router: APIRouter, container: AppContainer, services: AccessServices) -> None:
    CurrentAccount = Annotated[AuthenticatedAccount, Depends(require_account(container))]

    @router.get("/me/password", response_model=PasswordState, operation_id="getPasswordStatus")
    def get_password_status(account: CurrentAccount):
        with access_errors():
            return PasswordState(configured=services.password_setup.status(account))

    @router.put("/me/password", response_model=PasswordConfigured, operation_id="setInitialPassword")
    def set_initial_password(
        body: SetInitialPasswordRequest, idempotency_key: IdempotencyKey, account: CurrentAccount, request: Request,
    ):
        with access_errors():
            return services.password_setup.set_password(
                account, body.password.get_secret_value(), idempotency_key,
                request.client.host if request.client else "unknown",
            )
