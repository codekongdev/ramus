"""Dependencies the composition root hands to every module's ``register`` function."""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import FastAPI
from sqlalchemy.orm import Session

from ramus_api.settings import Settings
from ramus_api.shared.application import IdempotentExecutor
from ramus_api.shared.infrastructure import Database


@dataclass(frozen=True)
class AppContainer:
    settings: Settings
    database: Database
    idempotency: IdempotentExecutor[Session]


ModuleRegistrar = Callable[[FastAPI, AppContainer], None]
