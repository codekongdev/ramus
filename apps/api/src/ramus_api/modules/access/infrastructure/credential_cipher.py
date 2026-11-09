"""Authenticated AES-GCM encryption, bound to the owning account to prevent ciphertext swapping."""

import base64
import binascii
import hashlib
import hmac
import secrets
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import SecretStr

from ramus_api.modules.access.application.errors import SERVICE_UNAVAILABLE, AccessRejected


class AesCredentialCipher:
    def __init__(self, secret: SecretStr | None) -> None:
        self._secret = secret

    def _key(self) -> bytes:
        try:
            if self._secret is None:
                raise ValueError
            encoded = self._secret.get_secret_value()
            key = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
            if len(key) != 32:
                raise ValueError
            return key
        except (ValueError, binascii.Error):
            raise AccessRejected(SERVICE_UNAVAILABLE) from None

    def encrypt(self, account_id: UUID, api_key: str) -> str:
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(self._key()).encrypt(nonce, api_key.encode(), account_id.bytes)
        return "v1." + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, account_id: UUID, ciphertext: str) -> str:
        key = self._key()
        try:
            if not ciphertext.startswith("v1."):
                raise ValueError
            encrypted = base64.b64decode(ciphertext[3:], altchars=b"-_", validate=True)
            return AESGCM(key).decrypt(encrypted[:12], encrypted[12:], account_id.bytes).decode()
        except (ValueError, InvalidTag, UnicodeError, binascii.Error):
            raise AccessRejected(SERVICE_UNAVAILABLE) from None

    def fingerprint(self, api_key: str) -> str:
        return hmac.new(self._key(), api_key.encode(), hashlib.sha256).hexdigest()
