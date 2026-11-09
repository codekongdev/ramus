"""Composition root: builds the container and registers every module.

Add a module by appending its ``register`` function to ``MODULES``.
There is no module-level app; servers use the factory (``uvicorn --factory ramus_api.main:create_app``).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial
from uuid import UUID

from fastapi import FastAPI
from sqlalchemy.orm import Session

from ramus_api.container import AppContainer, ModuleRegistrar
from ramus_api.modules.access.application.ports import Mailer
from ramus_api.modules.access.composition import build_authenticator
from ramus_api.modules.access.infrastructure.mailer import LoggingMailer
from ramus_api.modules.access.infrastructure.stores import SqlAccountStore
from ramus_api.modules.access.presentation.routes import register as register_access
from ramus_api.modules.access.public import MembershipReader
from ramus_api.modules.conversations.presentation.routes import register as register_conversations
from ramus_api.modules.execution.presentation.routes import register as register_execution
from ramus_api.modules.projects.infrastructure.sample import (
    SHARED_SAMPLE_PROJECT_ID,
    ensure_shared_sample_project,
)
from ramus_api.modules.projects.presentation.routes import register as register_projects
from ramus_api.modules.realtime.presentation.routes import register as register_realtime
from ramus_api.modules.resources.presentation.routes import register as register_resources
from ramus_api.modules.results.presentation.routes import register as register_results
from ramus_api.modules.sharing.presentation.routes import register as register_sharing
from ramus_api.modules.system.presentation.routes import register as register_system
from ramus_api.settings import Settings
from ramus_api.shared.infrastructure import Database, SqlIdempotentExecutor
from ramus_api.shared.presentation import ERROR_RESPONSES, install_error_handlers

API_TITLE = "Ramus API"
API_VERSION = "0.1.0"


class SharedSampleProject:
    """Connects access's ``SharedProjectProvider`` port to the projects module's shared sample."""

    @property
    def project_id(self) -> UUID:
        return SHARED_SAMPLE_PROJECT_ID

    def ensure_shared_project(self, transaction: Session) -> UUID:
        return ensure_shared_sample_project(transaction)


MODULES: tuple[ModuleRegistrar, ...] = (
    register_system,
    partial(register_access, shared_project=SharedSampleProject()),
    partial(register_projects, memberships=MembershipReader(SqlAccountStore())),
    register_conversations,
    register_execution,
    register_realtime,
    register_resources,
    register_results,
    register_sharing,
)


def build_container(settings: Settings, mailer: Mailer | None = None) -> AppContainer:
    """``mailer`` defaults to the development ``LoggingMailer``, which prints codes to the server log."""
    database = Database(settings.database_url)
    return AppContainer(
        settings=settings,
        database=database,
        idempotency=SqlIdempotentExecutor(database),
        mailer=mailer if mailer is not None else LoggingMailer(),
        authenticator=build_authenticator(database),
    )


def create_app(settings: Settings | None = None, *, mailer: Mailer | None = None) -> FastAPI:
    """Builds the app without connecting to the database; connections open on first use."""
    container = build_container(settings or Settings(), mailer)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            container.database.dispose()

    app = FastAPI(title=API_TITLE, version=API_VERSION, lifespan=lifespan, responses=ERROR_RESPONSES)
    app.state.container = container
    install_error_handlers(app)
    for register in MODULES:
        register(app, container)
    return app
