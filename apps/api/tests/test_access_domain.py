"""Pure login rules: email normalization, code/token hashing, resend interval, and code checks."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from ramus_api.modules.access.domain.codes import (
    CODE_LENGTH,
    CODE_TTL,
    MAX_CODE_ATTEMPTS,
    RESEND_INTERVAL,
    SESSION_TTL,
    CodeVerdict,
    EmailCodeState,
    can_resend,
    code_expires_at,
    format_code,
    hash_code,
    hash_session_token,
    judge_code,
    resend_available_at,
    session_expires_at,
    to_iso_utc,
)
from ramus_api.modules.access.domain.email import (
    MAX_DISPLAY_NAME_LENGTH,
    InvalidEmail,
    display_name_for,
    normalize_email,
)

NOW = datetime(2026, 11, 9, 4, 17, 23, tzinfo=UTC)
CODE_ID = UUID(int=7)


def test_contract_constants() -> None:
    assert CODE_LENGTH == 6
    assert CODE_TTL == timedelta(minutes=10)
    assert MAX_CODE_ATTEMPTS == 5
    assert RESEND_INTERVAL == timedelta(seconds=60)
    assert SESSION_TTL == timedelta(days=14)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("user@example.com", "user@example.com"),
        ("  User@Example.COM  ", "user@example.com"),
        ("\tMixed.Case+tag@Sub.Example.org\n", "mixed.case+tag@sub.example.org"),
    ],
)
def test_normalize_email_trims_and_lowercases(raw: str, expected: str) -> None:
    assert normalize_email(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "no-at-sign.example.com",
        "two@@example.com",
        "a@b@example.com",
        "@example.com",
        "user@",
        "user@localhost",
        "us er@example.com",
        "user@exa mple.com",
        "user\t@example.com",
    ],
)
def test_normalize_email_rejects_malformed_addresses(raw: str) -> None:
    with pytest.raises(InvalidEmail):
        normalize_email(raw)


def test_invalid_email_is_a_value_error_without_the_address() -> None:
    with pytest.raises(ValueError) as caught:
        normalize_email("secret-address-at-example")
    assert "secret-address-at-example" not in str(caught.value)


def test_display_name_is_the_local_part() -> None:
    assert display_name_for("mason.kim@example.com") == "mason.kim"


def test_display_name_is_capped() -> None:
    local = "a" * (MAX_DISPLAY_NAME_LENGTH + 20)
    assert display_name_for(f"{local}@example.com") == "a" * MAX_DISPLAY_NAME_LENGTH


def test_format_code_zero_pads_to_six_digits() -> None:
    assert format_code(42) == "000042"
    assert format_code(999_999) == "999999"
    with pytest.raises(ValueError):
        format_code(1_000_000)
    with pytest.raises(ValueError):
        format_code(-1)


def test_code_hash_is_deterministic_salted_and_not_the_code() -> None:
    first = hash_code("123456", str(CODE_ID))
    assert first == hash_code("123456", str(CODE_ID))
    assert "123456" not in first
    assert first != hash_code("123456", str(UUID(int=8)))
    assert first != hash_code("123457", str(CODE_ID))


def test_session_token_hash_is_deterministic_and_not_the_token() -> None:
    token = "example-session-token-value"
    digest = hash_session_token(token)
    assert digest == hash_session_token(token)
    assert token not in digest
    assert digest != hash_session_token(token + "x")


def test_resend_interval_boundaries() -> None:
    assert can_resend(None, NOW)
    assert not can_resend(NOW - timedelta(seconds=59), NOW)
    assert not can_resend(NOW - timedelta(seconds=59, microseconds=999_999), NOW)
    assert can_resend(NOW - timedelta(seconds=60), NOW)
    assert resend_available_at(NOW) == NOW + timedelta(seconds=60)


def test_expiry_helpers() -> None:
    assert code_expires_at(NOW) == NOW + timedelta(minutes=10)
    assert session_expires_at(NOW) == NOW + timedelta(days=14)


def test_iso_utc_uses_z_suffix() -> None:
    assert to_iso_utc(NOW) == "2026-11-09T04:17:23Z"


def _state(**changes) -> EmailCodeState:
    base = EmailCodeState(
        id=CODE_ID,
        code_hash=hash_code("123456", str(CODE_ID)),
        expires_at=NOW + timedelta(minutes=1),
        attempts=0,
        consumed_at=None,
    )
    return replace(base, **changes)


def test_matching_code_is_verified() -> None:
    assert judge_code(_state(), "123456", NOW) is CodeVerdict.VERIFIED


def test_mismatching_code_is_invalid() -> None:
    assert judge_code(_state(), "654321", NOW) is CodeVerdict.INVALID


def test_missing_code_is_expired() -> None:
    assert judge_code(None, "123456", NOW) is CodeVerdict.EXPIRED


def test_expiry_boundary() -> None:
    expires = NOW + timedelta(minutes=1)
    state = _state(expires_at=expires)
    assert judge_code(state, "123456", expires - timedelta(microseconds=1)) is CodeVerdict.VERIFIED
    assert judge_code(state, "123456", expires) is CodeVerdict.EXPIRED


def test_exhausted_attempts_are_expired_even_with_the_right_code() -> None:
    assert judge_code(_state(attempts=MAX_CODE_ATTEMPTS - 1), "123456", NOW) is CodeVerdict.VERIFIED
    assert judge_code(_state(attempts=MAX_CODE_ATTEMPTS), "123456", NOW) is CodeVerdict.EXPIRED


def test_consumed_code_is_expired() -> None:
    assert judge_code(_state(consumed_at=NOW), "123456", NOW) is CodeVerdict.EXPIRED
