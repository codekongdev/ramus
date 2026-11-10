"""Password boundary and KDF checks without network or database access."""

import pytest
from pydantic import ValidationError

from ramus_api.modules.access.infrastructure.passwords import ScryptPasswordHasher
from ramus_api.modules.access.presentation.dto import PasswordLoginRequest, RegisterAccountRequest


def test_hashing_is_salted_and_preserves_whitespace_and_unicode():
    hasher = ScryptPasswordHasher()
    password = "  암호 문장 그대로 유지  "
    first, second = hasher.hash(password), hasher.hash(password)
    assert first != second
    assert password not in first
    assert hasher.verify(password, first)
    assert not hasher.verify(password.strip(), first)
    assert not hasher.verify(password, None)
    assert not hasher.verify(password, "invalid")


@pytest.mark.parametrize("password", ["short", "x" * 129, "bad\x00password-text", "bad\ud800password-text"])
def test_password_boundary_rejects_invalid_values(password):
    with pytest.raises(ValidationError):
        PasswordLoginRequest(email="test@example.test", password=password)


def test_password_boundary_never_strips_or_exposes_password():
    password = "  correct-password  "
    dto = RegisterAccountRequest(email=" A@EXAMPLE.TEST ", password=password, display_name="  닉네임  ")
    assert dto.password.get_secret_value() == password
    assert dto.email == "a@example.test" and dto.display_name == "닉네임"
    assert password not in repr(dto)


@pytest.mark.parametrize("name", [" ", "a\x00b", "a\u200bb", "x" * 101])
def test_display_name_boundary(name):
    with pytest.raises(ValidationError):
        RegisterAccountRequest(email="a@example.test", password="correct-password", display_name=name)


def test_deployed_password_auth_requires_a_stable_secret():
    from ramus_api.main import create_app
    from ramus_api.settings import Settings

    settings = Settings(_env_file=None, RAMUS_ENV="production",
                        database_url="postgresql+psycopg://nobody:nothing@127.0.0.1:1/nowhere")
    with pytest.raises(ValueError, match="stable RAMUS_AUTH_SECRET"):
        create_app(settings)


def test_password_setup_rechecks_expiry_after_obtaining_the_session_lock():
    from contextlib import contextmanager
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from ramus_api.modules.access.application.errors import AccessRejected
    from ramus_api.modules.access.application.password_setup import PasswordSetup
    from ramus_api.modules.access.application.ports import PasswordSetupSession
    from ramus_api.modules.access.domain.models import AuthenticatedAccount

    before = datetime(2026, 1, 1, tzinfo=UTC)
    deadline = before + timedelta(seconds=1)

    class Clock:
        value = before

        def now(self):
            return self.value

    clock = Clock()

    class Sessions:
        def lock_for_account(self, transaction, session_id, account_id):
            # Model a row lock that becomes available only after the session expires.
            clock.value = deadline + timedelta(seconds=1)
            return PasswordSetupSession(deadline, None)

    class Accounts:
        def password_configured(self, transaction, account_id):
            pytest.fail("An expired session must not read password configuration")

    @contextmanager
    def transactions():
        yield object()

    service = PasswordSetup(transactions, Accounts(), Sessions(), None, None, clock, None, "synthetic-secret")
    account = AuthenticatedAccount(uuid4(), "test@example.test", "테스트", uuid4())
    with pytest.raises(AccessRejected) as rejected:
        service.status(account)
    assert rejected.value.code == "UNAUTHORIZED"
