"""Ports the access use cases depend on. Implementations are injected by the composition root.

Store methods run inside the caller's transaction (``TransactionT``); the use case decides its scope.
"""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.access.domain.codes import EmailCodeState
from ramus_api.modules.access.domain.credentials import StoredCredential
from ramus_api.modules.access.domain.models import (
    AccountProfile,
    AIConnectionStatus,
    AuthenticatedAccount,
    MembershipRole,
)
from ramus_api.shared.application.notifications import Mailer as Mailer

TransactionT = TypeVar("TransactionT", contravariant=True)
TransactionT_co = TypeVar("TransactionT_co", covariant=True)


class CredentialProvider(Protocol):
    """Executor-only access. Never store its return value in a run, event, or log."""

    def get_api_key(self, account_id: UUID) -> str: ...


class ProjectAccess(Protocol[TransactionT]):
    """Public project authorization and safe author labels; no account credentials are exposed."""

    def require_member(self, transaction: TransactionT, project_id: UUID, account_id: UUID) -> None: ...

    def display_names(self, transaction: TransactionT, account_ids: set[UUID]) -> dict[UUID, str]: ...


class AiKeyValidator(Protocol):
    async def validate(self, api_key: str) -> None:
        """Checks model access; failures must not retain or expose the supplied key."""


class CredentialCipher(Protocol):
    def encrypt(self, account_id: UUID, api_key: str) -> str: ...

    def decrypt(self, account_id: UUID, ciphertext: str) -> str: ...

    def fingerprint(self, api_key: str) -> str: ...


class AiConnectionStore(Protocol[TransactionT]):
    def get(self, transaction: TransactionT, account_id: UUID) -> StoredCredential | None: ...

    def save(self, transaction: TransactionT, account_id: UUID, credential: StoredCredential) -> None: ...

    def delete(self, transaction: TransactionT, account_id: UUID) -> None: ...

    def is_connected(self, transaction: TransactionT, account_id: UUID) -> bool: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class SecretSource(Protocol):
    """Cryptographically secure randomness for login codes and session tokens."""

    def new_code(self) -> str: ...

    def new_session_token(self) -> str: ...


class TransactionFactory(Protocol[TransactionT_co]):
    """Opens a transaction that commits on normal exit and rolls back on error."""

    def __call__(self) -> AbstractContextManager[TransactionT_co]: ...


@dataclass(frozen=True)
class NewEmailCode:
    id: UUID
    email: str
    code_hash: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class NewSession:
    id: UUID
    account_id: UUID
    token_hash: str
    created_at: datetime
    expires_at: datetime


class EmailCodeStore(Protocol[TransactionT]):
    def lock_email(self, transaction: TransactionT, email: str) -> None:
        """Serializes code requests for one address until the transaction ends."""

    def latest_created_at(self, transaction: TransactionT, email: str) -> datetime | None: ...

    def add(self, transaction: TransactionT, code: NewEmailCode) -> None: ...

    def lock_latest(self, transaction: TransactionT, email: str) -> EmailCodeState | None:
        """Returns the newest code for ``email`` and row-locks it until the transaction ends."""

    def record_failed_attempt(self, transaction: TransactionT, code_id: UUID) -> None: ...

    def consume(self, transaction: TransactionT, code_id: UUID, at: datetime) -> None: ...


class AccountStore(Protocol[TransactionT]):
    def ensure_account(self, transaction: TransactionT, email: str, display_name: str) -> UUID:
        """Creates the account if the email is new; otherwise returns the existing ID unchanged."""

    def add_membership(
        self, transaction: TransactionT, account_id: UUID, project_id: UUID, role: MembershipRole
    ) -> None:
        """Adds the membership; an existing one is left as it is."""

    def get_profile(self, transaction: TransactionT, account_id: UUID) -> AccountProfile | None: ...

    def project_ids(self, transaction: TransactionT, account_id: UUID) -> list[UUID]: ...

    def participants(self, transaction: TransactionT, project_id: UUID) -> list[AccountProfile]: ...

    def ai_connection_status(self, transaction: TransactionT, account_id: UUID) -> AIConnectionStatus: ...


class SessionStore(Protocol[TransactionT]):
    def add(self, transaction: TransactionT, session: NewSession) -> None: ...

    def find_active(
        self, transaction: TransactionT, token_hash: str, now: datetime
    ) -> AuthenticatedAccount | None:
        """The unrevoked, unexpired session with this digest and its account."""

    def revoke(self, transaction: TransactionT, token_hash: str, at: datetime) -> None:
        """Marks the session revoked; an already revoked or unknown session is left as it is."""


class SharedProjectProvider(Protocol[TransactionT]):
    """The projects module's shared sample project, seen from access. Access never writes ``project``."""

    @property
    def project_id(self) -> UUID: ...

    def ensure_shared_project(self, transaction: TransactionT) -> UUID: ...
