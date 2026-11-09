"""Builds the access use cases from the shared container and the module's SQL adapters."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from ramus_api.container import AppContainer
from ramus_api.modules.access.application.ai_connection import AiConnections
from ramus_api.modules.access.application.login import RequestEmailCode, VerifyEmailCode
from ramus_api.modules.access.application.ports import SharedProjectProvider
from ramus_api.modules.access.application.rate_limits import AuthRateLimiter
from ramus_api.modules.access.application.sessions import Authenticator, ProfileReader, SessionIssuer
from ramus_api.modules.access.infrastructure.ai_connections import SqlAiConnectionStore
from ramus_api.modules.access.infrastructure.credential_cipher import AesCredentialCipher
from ramus_api.modules.access.infrastructure.rate_limits import SqlAttemptStore
from ramus_api.modules.access.infrastructure.stores import SqlAccountStore, SqlEmailCodeStore, SqlSessionStore
from ramus_api.modules.access.infrastructure.system import SystemClock, SystemSecretSource
from ramus_api.shared.application.identity import SessionAuthenticator
from ramus_api.shared.infrastructure import Database


@dataclass(frozen=True)
class AccessServices:
    request_email_code: RequestEmailCode[Session]
    verify_email_code: VerifyEmailCode[Session]
    authenticator: SessionAuthenticator
    profiles: ProfileReader[Session]
    ai_connections: AiConnections[Session]


def build_ai_connections(container: AppContainer) -> AiConnections[Session]:
    """Public builder providing both execution AiConnectionQuery and access CredentialProvider."""
    return AiConnections(
        container.database.transaction,
        container.idempotency,
        SqlAiConnectionStore(),
        container.ai_key_validator,
        AesCredentialCipher(container.settings.secret_key),
        SystemClock(),
    )


def build_authenticator(database: Database) -> Authenticator[Session]:
    return Authenticator(database.transaction, SqlSessionStore(), SystemClock())


def build_access_services(
    container: AppContainer, shared_project: SharedProjectProvider[Session]
) -> AccessServices:
    database = container.database
    clock, secrets = SystemClock(), SystemSecretSource()
    codes, accounts, sessions = SqlEmailCodeStore(), SqlAccountStore(), SqlSessionStore()
    profiles = ProfileReader(database.transaction, accounts, shared_project, sessions, clock)
    secret = container.settings.auth_secret.get_secret_value()
    limits = AuthRateLimiter(database.transaction, SqlAttemptStore(), clock, secret)
    issuer = SessionIssuer(database.transaction, sessions, profiles, clock, secrets)
    return AccessServices(
        request_email_code=RequestEmailCode(
            container.idempotency, codes, container.mailer, clock, secrets, limits, secret
        ),
        verify_email_code=VerifyEmailCode(
            container.idempotency, codes, accounts, shared_project, issuer, clock, limits, secret
        ),
        authenticator=container.authenticator,
        profiles=profiles,
        ai_connections=build_ai_connections(container),
    )
