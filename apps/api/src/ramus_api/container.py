"""Dependencies the composition root hands to every module's ``register`` function."""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import FastAPI
from sqlalchemy.orm import Session

from ramus_api.modules.access.application.ports import AiKeyValidator, ProjectAccess
from ramus_api.modules.conversations.application.ports import RunReader
from ramus_api.modules.execution.application.ports import RunRequester
from ramus_api.modules.execution.application.relay import EventRelay
from ramus_api.modules.execution.application.runtime_ports import TransactionHooks
from ramus_api.modules.execution.composition import ExecutionRuntime
from ramus_api.modules.realtime.application.ports import EventBroker
from ramus_api.settings import Settings
from ramus_api.shared.application import IdempotentExecutor
from ramus_api.shared.application.identity import SessionAuthenticator
from ramus_api.shared.application.notifications import Mailer
from ramus_api.shared.infrastructure import Database


@dataclass(frozen=True)
class AppContainer:
    settings: Settings
    database: Database
    idempotency: IdempotentExecutor[Session]
    mailer: Mailer
    authenticator: SessionAuthenticator
    project_access: ProjectAccess[Session]
    events: EventBroker
    event_relay: EventRelay
    event_hooks: TransactionHooks[Session]
    run_requester: RunRequester[Session]
    run_reader: RunReader[Session]
    ai_key_validator: AiKeyValidator
    execution_runtime: ExecutionRuntime | None = None


ModuleRegistrar = Callable[[FastAPI, AppContainer], None]
