"""Realtime endpoint: the project event stream (docs/contracts.md section 4). A stub until the SSE task."""

from uuid import UUID

from fastapi import APIRouter, FastAPI
from fastapi.responses import StreamingResponse

from ramus_api.container import AppContainer
from ramus_api.shared.presentation.error_messages import not_implemented

EVENT_STREAM = "text/event-stream"


class EventStreamResponse(StreamingResponse):
    """Declares ``text/event-stream`` as the route's only success media type in OpenAPI."""

    media_type = EVENT_STREAM


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["realtime"])

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
    def stream_project_events(project_id: UUID):
        raise not_implemented()

    app.include_router(router)
