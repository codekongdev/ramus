"""Composition root: builds the container and registers every module.

Add a module by appending its ``register`` function to ``MODULES``.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ramus_api.container import AppContainer, ModuleRegistrar
from ramus_api.modules import system
from ramus_api.settings import Settings
from ramus_api.shared.infrastructure import Database, SqlIdempotentExecutor
from ramus_api.shared.presentation import ERROR_RESPONSES, install_error_handlers

API_TITLE = "Ramus API"
API_VERSION = "0.1.0"

MODULES: tuple[ModuleRegistrar, ...] = (
    system.register,
)


def build_container(settings: Settings) -> AppContainer:
    database = Database(settings.database_url)
    return AppContainer(settings=settings, database=database, idempotency=SqlIdempotentExecutor(database))


def create_app(settings: Settings | None = None) -> FastAPI:
    """Builds the app without connecting to the database; connections open on first use."""
    container = build_container(settings or Settings())

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


app = create_app()
