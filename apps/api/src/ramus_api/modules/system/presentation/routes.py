from typing import Literal

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from ramus_api.container import AppContainer


class HealthResponse(BaseModel):
    status: Literal["ok"]


def register(app: FastAPI, container: AppContainer) -> None:
    router = APIRouter(prefix="/api", tags=["system"])

    @router.get("/health", response_model=HealthResponse, operation_id="getHealth")
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    app.include_router(router)
