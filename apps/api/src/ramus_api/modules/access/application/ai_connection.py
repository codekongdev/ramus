"""Account-scoped connection management. Provider I/O precedes the short save transaction."""

from typing import Generic, TypeVar
from uuid import UUID

from ramus_api.modules.access.application.errors import (
    AI_CONNECTION_REQUIRED,
    AI_KEY_INVALID,
    SERVICE_UNAVAILABLE,
    AccessRejected,
)
from ramus_api.modules.access.application.ports import (
    AiConnectionStore,
    AiKeyValidator,
    Clock,
    CredentialCipher,
    TransactionFactory,
)
from ramus_api.modules.access.domain.credentials import StoredCredential
from ramus_api.modules.access.domain.models import AIConnectionStatus
from ramus_api.shared.application import IdempotentExecutor

TransactionT = TypeVar("TransactionT")


class AiConnections(Generic[TransactionT]):
    def __init__(
        self,
        transaction: TransactionFactory[TransactionT],
        idempotency: IdempotentExecutor[TransactionT],
        store: AiConnectionStore[TransactionT],
        validator: AiKeyValidator,
        cipher: CredentialCipher,
        clock: Clock,
    ) -> None:
        self._transaction = transaction
        self._idempotency = idempotency
        self._store = store
        self._validator = validator
        self._cipher = cipher
        self._clock = clock

    def status(self, account_id: UUID) -> AIConnectionStatus:
        with self._transaction() as transaction:
            credential = self._store.get(transaction, account_id)
            return AIConnectionStatus.NONE if credential is None else credential.status

    async def connect(self, account_id: UUID, api_key: str, request_key: str) -> None:
        api_key = api_key.strip()
        if not api_key or any(character.isspace() for character in api_key):
            raise AccessRejected(AI_KEY_INVALID)
        # Fail closed before spending a validation call when server encryption is unavailable.
        ciphertext = self._cipher.encrypt(account_id, api_key)
        payload = {"credential_fingerprint": self._cipher.fingerprint(api_key)}
        try:
            await self._validator.validate(api_key)
        except AccessRejected:
            raise
        except Exception:
            # Injected validators must not get a chance to leak an SDK exception containing a key.
            raise AccessRejected(SERVICE_UNAVAILABLE) from None
        credential = StoredCredential(ciphertext, AIConnectionStatus.CONNECTED, self._clock.now())

        def save(transaction: TransactionT) -> dict:
            self._store.save(transaction, account_id, credential)
            return {"status": AIConnectionStatus.CONNECTED.value}

        self._idempotency.execute_once(str(account_id), "access.connect_ai", request_key, payload, save)

    def disconnect(self, account_id: UUID, request_key: str) -> None:
        def delete(transaction: TransactionT) -> dict:
            self._store.delete(transaction, account_id)
            return {"status": AIConnectionStatus.NONE.value}

        self._idempotency.execute_once(str(account_id), "access.disconnect_ai", request_key, {}, delete)

    def get_api_key(self, account_id: UUID) -> str:
        """Executor-only: look up each time so a deleted/invalid connection stops queued runs."""
        with self._transaction() as transaction:
            credential = self._store.get(transaction, account_id)
        if credential is None or credential.status != AIConnectionStatus.CONNECTED:
            raise AccessRejected(AI_CONNECTION_REQUIRED)
        return self._cipher.decrypt(account_id, credential.ciphertext)

    def is_connected(self, transaction: TransactionT, account_id: UUID) -> bool:
        return self._store.is_connected(transaction, account_id)
