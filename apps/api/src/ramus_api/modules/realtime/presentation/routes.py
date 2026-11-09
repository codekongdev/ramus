"""Authenticated, project-scoped event stream (docs/contracts.md section 4)."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from starlette.types import Receive, Scope, Send

from ramus_api.container import AppContainer
from ramus_api.modules.access.presentation.current_account import AuthenticatedAccount, require_account
from ramus_api.modules.realtime.presentation.stream import stream_events

EVENT_STREAM = "text/event-stream"


class EventStreamResponse(StreamingResponse):
    """Declares ``text/event-stream`` as the route's only success media type in OpenAPI."""

    media_type = EVENT_STREAM

    def __init__(
        self, content, status_code: int = 200, *, close: Callable[[], None] | None = None, **kwargs
    ) -> None:
        super().__init__(content, status_code=status_code, **kwargs)
        self._close = close

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            # Also clean up a disconnect during response headers, before iteration even starts.
            if self._close is not None:
                self._close()


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["realtime"])
    current_account = require_account(container)
    CurrentAccount = Annotated[AuthenticatedAccount, Depends(current_account)]

    @router.get(
        "/projects/{project_id}/events",
        operation_id="streamProjectEvents",
        response_class=EventStreamResponse,
        responses={
            200: {
                "description": "Server-sent events: `event: <name>` and `data: <JSON>`, `: ping` every 15 seconds.",
                "content": {EVENT_STREAM: {"schema": {"type": "string"}}},
            }
        },
    )
    async def stream_project_events(project_id: UUID, request: Request, account: CurrentAccount):
        def check_membership() -> None:
            with container.database.transaction() as session:
                container.project_access.require_member(session, project_id, account.account_id)

        await run_in_threadpool(check_membership)

        async def authorize() -> None:
            await run_in_threadpool(current_account, request)
            await run_in_threadpool(check_membership)

        subscription = container.events.subscribe(project_id)
        return EventStreamResponse(
            stream_events(subscription, authorize),
            close=subscription.close,
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    app.include_router(router)
