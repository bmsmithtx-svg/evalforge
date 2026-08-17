from __future__ import annotations

from uuid import UUID

from evalforge_api.domain.duplicate_detection import (
    compute_dedup_hash,
    find_duplicate_ids,
    normalize_text_input,
)
from evalforge_api.domain.test_case_content import TestCaseContent


def test_identical_content_produces_identical_hashes() -> None:
    left = compute_dedup_hash(TestCaseContent(input="What is 2 + 2?"))
    right = compute_dedup_hash(TestCaseContent(input="What is 2 + 2?"))
    assert left == right


def test_whitespace_and_case_differences_are_normalized_away() -> None:
    canonical = compute_dedup_hash(TestCaseContent(input="what is 2 + 2?"))
    noisy = compute_dedup_hash(TestCaseContent(input="  What   IS  2 + 2? \n"))
    assert canonical == noisy


def test_materially_different_input_produces_a_different_hash() -> None:
    left = compute_dedup_hash(TestCaseContent(input="What is 2 + 2?"))
    right = compute_dedup_hash(TestCaseContent(input="What is 2 + 3?"))
    assert left != right


def test_only_input_participates_in_the_duplicate_rule() -> None:
    """Same input, different expected output: still an exact duplicate
    by input, which is precisely the conflict worth surfacing."""
    left = compute_dedup_hash(TestCaseContent(input="2 + 2", expected_output="4"))
    right = compute_dedup_hash(TestCaseContent(input="2 + 2", expected_output="four"))
    assert left == right


def test_structured_input_key_order_does_not_change_the_hash() -> None:
    left = compute_dedup_hash(TestCaseContent(input={"a": 1, "b": 2}))
    right = compute_dedup_hash(TestCaseContent(input={"b": 2, "a": 1}))
    assert left == right


def test_structured_and_text_inputs_never_collide() -> None:
    text = compute_dedup_hash(TestCaseContent(input="value"))
    structured = compute_dedup_hash(TestCaseContent(input={"value": "value"}))
    assert text != structured


def test_normalize_text_input_collapses_all_whitespace_runs() -> None:
    assert normalize_text_input("  A \t B \n\n C ") == "a b c"


def test_find_duplicate_ids_returns_every_match_in_deterministic_order() -> None:
    first = UUID("00000000-0000-0000-0000-000000000002")
    second = UUID("00000000-0000-0000-0000-000000000001")
    third = UUID("00000000-0000-0000-0000-000000000003")
    existing = {first: "hash-a", second: "hash-a", third: "hash-b"}
    assert find_duplicate_ids("hash-a", existing) == (second, first)


def test_find_duplicate_ids_returns_nothing_when_the_mapping_is_empty() -> None:
    assert find_duplicate_ids("hash-a", {}) == ()
