from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

import pytest

from ramus_api.shared.domain import fingerprint, is_valid_idempotency_key


def test_fingerprint_ignores_key_order_at_every_depth() -> None:
    first = {"b": 1, "a": {"y": [1, 2], "x": "값"}}
    second = {"a": {"x": "값", "y": [1, 2]}, "b": 1}
    assert fingerprint(first) == fingerprint(second)


def test_fingerprint_is_sha256_hex() -> None:
    value = fingerprint({"a": 1})
    assert len(value) == 64
    assert int(value, 16) >= 0


def test_fingerprint_differs_for_different_payloads() -> None:
    assert fingerprint({"a": 1}) != fingerprint({"a": 2})
    assert fingerprint({"items": [1, 2]}) != fingerprint({"items": [2, 1]})


def test_fingerprint_rejects_non_json_payloads() -> None:
    with pytest.raises(TypeError):
        fingerprint({"value": object()})


@pytest.mark.parametrize("key", ["a", "A1._:-", "x" * 128, "550e8400-e29b-41d4-a716-446655440000"])
def test_valid_idempotency_keys(key: str) -> None:
    assert is_valid_idempotency_key(key)


@pytest.mark.parametrize("key", ["", "x" * 129, "has space", "슬래시/", "a/b", "tab\t", "new\nline", "키"])
def test_invalid_idempotency_keys(key: str) -> None:
    assert not is_valid_idempotency_key(key)


class Color(Enum):
    RED = "red"


def test_fingerprint_accepts_common_non_json_values() -> None:
    identifier = UUID("550e8400-e29b-41d4-a716-446655440000")
    moment = datetime(2026, 11, 9, 13, 0, tzinfo=UTC)
    payload = {
        "id": identifier,
        "at": moment,
        "day": date(2026, 11, 9),
        "amount": Decimal("12.50"),
        "color": Color.RED,
    }
    expected = {
        "id": str(identifier),
        "at": moment.isoformat(),
        "day": "2026-11-09",
        "amount": "12.50",
        "color": "red",
    }
    assert fingerprint(payload) == fingerprint(expected)


def test_fingerprint_handles_model_dump_with_uuid() -> None:
    assert len(fingerprint({"id": uuid4(), "items": [{"at": datetime.now(UTC)}]})) == 64


def test_fingerprint_error_names_the_unsupported_type() -> None:
    class Unsupported:
        pass

    with pytest.raises(TypeError, match="Unsupported"):
        fingerprint({"value": Unsupported()})
