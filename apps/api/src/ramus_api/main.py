from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ramus_api.application.workspace import Workspace
from ramus_api.composition import SqlUnitOfWork
from ramus_api.infrastructure.database import Database
from ramus_api.presentation.dto import (
    CreateMessageRequest,
    CreateProjectRequest,
    ErrorResponseDTO,
    HealthDTO,
    Identifier,
    LoginRequest,
    MessagePostDTO,
    OkDTO,
    ProjectDTO,
    StateDTO,
    UserDTO,
)
from ramus_api.settings import Settings
from ramus_api.shared.domain import BusinessError

COOKIE_NAME = "ramus_session"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    database = Database(settings.database_url)
    workspace = Workspace(SqlUnitOfWork(database))

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            database.close()

    errors = {status: {"model": ErrorResponseDTO} for status in (401, 403, 404, 409, 422)}
    app = FastAPI(title="Ramus API", version="0.1.0", lifespan=lifespan, responses=errors)
    app.state.database, app.state.workspace, app.state.settings = database, workspace, settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def origin_boundary(request: Request, call_next):
        if request.method in {"POST", "PATCH", "DELETE", "PUT"}:
            origin = request.headers.get("origin")
            if (origin and origin not in settings.allowed_origins) or request.headers.get(
                "sec-fetch-site"
            ) == "cross-site":
                return JSONResponse(
                    {"error": {"code": "ORIGIN_FORBIDDEN", "message": "허용하지 않은 요청 출처입니다."}}, 403
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(BusinessError)
    async def business_error(_request: Request, exc: BusinessError):
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message, "details": exc.details}}, exc.status
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        details = [
            {
                "location": [part.encode("utf-8", errors="replace").decode("utf-8") if isinstance(part, str) else part
                             for part in error["loc"]],
                "type": error["type"], "message": error["msg"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            {"error": {"code": "INVALID_INPUT", "message": "입력 형식을 확인해 주세요.", "details": details}},
            422,
        )

    def current_user(request: Request) -> dict:
        return workspace.authenticate(request.cookies.get(COOKIE_NAME))

    @app.get("/api/health", response_model=HealthDTO, operation_id="health", tags=["system"])
    def health():
        return {"status": "ok", "service": "ramus"}

    @app.post("/api/auth/login", response_model=UserDTO, operation_id="login", tags=["access"])
    def login(data: LoginRequest, response: Response):
        user, token = workspace.login(data.email, data.password)
        response.set_cookie(
            COOKIE_NAME, token, max_age=43200, httponly=True,
            secure=settings.ramus_cookie_secure, samesite="lax", path="/",
        )
        return user

    @app.get("/api/auth/me", response_model=UserDTO, operation_id="me", tags=["access"])
    def me(user: dict = Depends(current_user)):
        return user

    @app.post("/api/auth/logout", response_model=OkDTO, operation_id="logout", tags=["access"])
    def logout(request: Request, response: Response):
        workspace.logout(request.cookies.get(COOKIE_NAME))
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"ok": True}

    @app.get("/api/projects", response_model=list[ProjectDTO], operation_id="listProjects", tags=["projects"])
    def projects(user: dict = Depends(current_user)):
        return workspace.projects(user)

    @app.post("/api/projects", response_model=ProjectDTO, operation_id="createProject", tags=["projects"])
    def create_project(data: CreateProjectRequest, user: dict = Depends(current_user)):
        return workspace.create_project(user, data.model_dump())

    @app.get("/api/state", response_model=StateDTO, operation_id="getState", tags=["workspace"])
    def state(project_id: Identifier | None = None, user: dict = Depends(current_user)):
        return workspace.state(user, project_id)

    @app.post(
        "/api/messages", response_model=MessagePostDTO, operation_id="appendMessage", tags=["conversations"]
    )
    def append_message(data: CreateMessageRequest, user: dict = Depends(current_user)):
        return workspace.append_message(user, data.model_dump())

    return app


app = create_app()
