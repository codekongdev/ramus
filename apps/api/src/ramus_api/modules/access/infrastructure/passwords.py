"""Salted scrypt password hashing; only this adapter performs the expensive KDF."""

import base64
import hashlib
import hmac
import secrets
from functools import lru_cache
from threading import BoundedSemaphore

N, R, P = 32768, 8, 3
_KDF_SLOTS = BoundedSemaphore(4)


def _derive(password: str, salt: bytes) -> bytes:
    with _KDF_SLOTS:
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=N, r=R, p=P, dklen=32, maxmem=64 * 1024 * 1024)


@lru_cache(maxsize=1)
def _dummy() -> tuple[bytes, bytes]:
    salt = b"ramus-dummy-salt"
    return salt, _derive("not-an-account-password", salt)


class ScryptPasswordHasher:
    def hash(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = _derive(password, salt)
        return f"scrypt${N}${R}${P}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"

    def verify(self, password: str, encoded: str | None) -> bool:
        valid = False
        salt, expected = _dummy()
        try:
            if encoded is not None:
                algorithm, n, r, p, raw_salt, raw_digest = encoded.split("$")
                if (algorithm, n, r, p) != ("scrypt", str(N), str(R), str(P)):
                    raise ValueError
                salt, expected = base64.b64decode(raw_salt, validate=True), base64.b64decode(raw_digest, validate=True)
                if len(salt) != 16 or len(expected) != 32:
                    raise ValueError
                valid = True
        except (ValueError, TypeError):
            salt, expected = _dummy()
        actual = _derive(password, salt)
        return hmac.compare_digest(actual, expected) and valid
