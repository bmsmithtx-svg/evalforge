from __future__ import annotations

import hashlib

from evalforge_api.domain.hashing import (
    CANONICALIZATION_VERSION,
    HASH_ALGORITHM,
    canonicalize_json,
    hash_bytes,
    hash_canonical_content,
)


def test_identical_content_with_different_key_order_hashes_the_same() -> None:
    a = {"prompt": "hello", "temperature": 0.2, "model": "gpt-x"}
    b = {"model": "gpt-x", "temperature": 0.2, "prompt": "hello"}

    assert hash_canonical_content(a) == hash_canonical_content(b)


def test_identical_nested_content_with_different_key_order_hashes_the_same() -> None:
    a = {"outer": {"z": 1, "a": 2}, "list": [{"y": 1, "x": 2}, {"b": 1, "a": 2}]}
    b = {"list": [{"x": 2, "y": 1}, {"a": 2, "b": 1}], "outer": {"a": 2, "z": 1}}

    assert hash_canonical_content(a) == hash_canonical_content(b)


def test_evaluation_significant_content_change_alters_the_hash() -> None:
    baseline = {"prompt": "You are a helpful assistant.", "temperature": 0.2}
    changed = {"prompt": "You are a helpful assistant!", "temperature": 0.2}

    assert hash_canonical_content(baseline) != hash_canonical_content(changed)


def test_canonicalize_json_is_deterministic_bytes() -> None:
    content = {"b": 2, "a": 1}
    assert canonicalize_json(content) == canonicalize_json({"a": 1, "b": 2})
    assert canonicalize_json(content) == b'{"a":1,"b":2}'


def test_hash_bytes_matches_sha256_reference_implementation() -> None:
    # Pins the algorithm choice against silent substitution — a
    # different algorithm producing a same-length hex digest would
    # otherwise pass every other test in this file undetected.
    payload = b"reference-payload-for-sha256-pinning"
    assert hash_bytes(payload) == hashlib.sha256(payload).hexdigest()
    assert hash_bytes(b"") == hashlib.sha256(b"").hexdigest()


def test_hash_bytes_changes_for_different_content() -> None:
    assert hash_bytes(b"content-a") != hash_bytes(b"content-b")


def test_hash_algorithm_and_canonicalization_version_are_recorded_constants() -> None:
    assert HASH_ALGORITHM == "sha256"
    assert CANONICALIZATION_VERSION
