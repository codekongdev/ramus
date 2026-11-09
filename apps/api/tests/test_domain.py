from ramus_api.shared.domain import canonical_hash, password_hash, password_matches, token_hash


def test_canonical_request_fingerprint_ignores_object_key_order():
    assert canonical_hash({"a": 1, "b": "한글"}) == canonical_hash({"b": "한글", "a": 1})
    assert canonical_hash({"content": "first"}) != canonical_hash({"content": "second"})


def test_password_hash_verifies_password_without_storing_plaintext():
    stored = password_hash("local-test-password", salt="00" * 16)
    assert "local-test-password" not in stored
    assert password_matches("local-test-password", stored)
    assert not password_matches("different", stored)
    assert not password_matches("local-test-password", "invalid")


def test_session_token_fingerprint_is_stable_and_does_not_store_the_token():
    assert token_hash("opaque-token") == token_hash("opaque-token")
    assert token_hash("opaque-token") != token_hash("another-token")
    assert "opaque-token" not in token_hash("opaque-token")
