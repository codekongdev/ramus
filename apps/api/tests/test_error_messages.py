"""The code -> message table that modules extend (roadmap 9.3 rule 2)."""

import pytest

from ramus_api.shared.presentation import error_messages


def test_not_implemented_has_a_korean_message() -> None:
    message = error_messages.message_for("NOT_IMPLEMENTED")
    assert any("가" <= ch <= "힣" for ch in message)


def test_modules_can_register_new_codes(monkeypatch) -> None:
    monkeypatch.setattr(error_messages, "_MESSAGES", dict(error_messages._MESSAGES))
    error_messages.register_error_messages({"SOME_NEW_CODE": "새 메시지입니다."})
    assert error_messages.message_for("SOME_NEW_CODE") == "새 메시지입니다."


def test_registering_the_same_message_twice_is_allowed(monkeypatch) -> None:
    monkeypatch.setattr(error_messages, "_MESSAGES", dict(error_messages._MESSAGES))
    error_messages.register_error_messages({"X": "같은 문장입니다."})
    error_messages.register_error_messages({"X": "같은 문장입니다."})


def test_registering_a_different_message_for_an_existing_code_fails(monkeypatch) -> None:
    monkeypatch.setattr(error_messages, "_MESSAGES", dict(error_messages._MESSAGES))
    with pytest.raises(ValueError, match="NOT_IMPLEMENTED"):
        error_messages.register_error_messages({"NOT_IMPLEMENTED": "다른 문장입니다."})


def test_not_implemented_error_is_a_501_business_error() -> None:
    error = error_messages.not_implemented()
    assert (error.code, error.status) == ("NOT_IMPLEMENTED", 501)
    assert error.message == error_messages.message_for("NOT_IMPLEMENTED")
