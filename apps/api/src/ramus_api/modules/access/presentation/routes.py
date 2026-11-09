"""Access endpoints: email-code login, session, and the account's AI connection. Stubs until P0-A4."""

from fastapi import APIRouter, FastAPI

from ramus_api.container import AppContainer
from ramus_api.modules.access.presentation.dto import (
    AiConnectionConnected,
    AiConnectionDisconnected,
    AiConnectionState,
    ConnectAiRequest,
    Me,
    RequestEmailCodeRequest,
    RequestEmailCodeResponse,
    VerifyEmailCodeRequest,
)
from ramus_api.shared.presentation.error_messages import not_implemented
from ramus_api.shared.presentation.idempotency import IdempotencyKey
from ramus_api.shared.presentation.schemas import EmptyRequest, EmptyResponse


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["access"])

    @router.post(
        "/auth/email-code",
        status_code=202,
        response_model=RequestEmailCodeResponse,
        operation_id="requestEmailCode",
    )
    def request_email_code(body: RequestEmailCodeRequest, idempotency_key: IdempotencyKey):
        raise not_implemented()

    @router.post("/auth/verify", response_model=Me, operation_id="verifyEmailCode")
    def verify_email_code(body: VerifyEmailCodeRequest, idempotency_key: IdempotencyKey):
        raise not_implemented()

    @router.post("/auth/logout", response_model=EmptyResponse, operation_id="logout")
    def logout(body: EmptyRequest, idempotency_key: IdempotencyKey):
        raise not_implemented()

    @router.get("/me", response_model=Me, operation_id="getMe")
    def get_me():
        raise not_implemented()

    @router.get("/me/ai-connection", response_model=AiConnectionState, operation_id="getAiConnection")
    def get_ai_connection():
        raise not_implemented()

    @router.put("/me/ai-connection", response_model=AiConnectionConnected, operation_id="connectAi")
    def connect_ai(body: ConnectAiRequest, idempotency_key: IdempotencyKey):
        raise not_implemented()

    @router.delete("/me/ai-connection", response_model=AiConnectionDisconnected, operation_id="disconnectAi")
    def disconnect_ai(idempotency_key: IdempotencyKey):
        raise not_implemented()

    app.include_router(router)
