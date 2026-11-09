"""Builds the access use cases from the shared container and the module's SQL adapters."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from ramus_api.container import AppContainer
from ramus_api.modules.access.application.login import RequestEmailCode, VerifyEmailCode
from ramus_api.modules.access.application.ports import SharedProjectProvider
from ramus_api.modules.access.application.sessions import Authenticator, ProfileReader, SessionIssuer
from ramus_api.modules.access.infrastructure.stores import SqlAccountStore, SqlEmailCodeStore, SqlSessionStore
from ramus_api.modules.access.infrastructure.system import SystemClock, SystemSecretSource
from ramus_api.shared.infrastructure import Database


@dataclass(frozen=True)
class AccessServices:
    request_email_code: RequestEmailCode[Session]
    verify_email_code: VerifyEmailCode[Session]
    authenticator: Authenticator[Session]
    profiles: ProfileReader[Session]


def build_authenticator(database: Database) -> Authenticator[Session]:
    return Authenticator(database.transaction, SqlSessionStore(), SystemClock())


def build_access_services(
    container: AppContainer, shared_project: SharedProjectProvider[Session]
) -> AccessServices:
    database = container.database
    clock, secrets = SystemClock(), SystemSecretSource()
    codes, accounts, sessions = SqlEmailCodeStore(), SqlAccountStore(), SqlSessionStore()
    profiles = ProfileReader(database.transaction, accounts, shared_project)
    issuer = SessionIssuer(database.transaction, sessions, profiles, clock, secrets)
    return AccessServices(
        request_email_code=RequestEmailCode(container.idempotency, codes, container.mailer, clock, secrets),
        verify_email_code=VerifyEmailCode(
            container.idempotency, codes, accounts, shared_project, issuer, clock
        ),
        authenticator=Authenticator(database.transaction, sessions, clock),
        profiles=profiles,
    )
