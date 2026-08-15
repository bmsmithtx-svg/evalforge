from __future__ import annotations

from evalforge_api.security.passwords import hash_password, verify_password

_CANDIDATE = "Correct-Horse-Battery-Staple-9"


def test_verify_password_accepts_the_original_plaintext() -> None:
    password_hash = hash_password(_CANDIDATE)
    assert verify_password(_CANDIDATE, password_hash) is True


def test_verify_password_rejects_a_wrong_plaintext() -> None:
    password_hash = hash_password(_CANDIDATE)
    assert verify_password("something-else-entirely", password_hash) is False


def test_hash_password_salts_each_call_differently() -> None:
    first = hash_password(_CANDIDATE)
    second = hash_password(_CANDIDATE)
    assert first != second
    assert verify_password(_CANDIDATE, first) is True
    assert verify_password(_CANDIDATE, second) is True


def test_verify_password_rejects_malformed_hash_instead_of_raising() -> None:
    assert verify_password(_CANDIDATE, "not-a-real-bcrypt-hash") is False
