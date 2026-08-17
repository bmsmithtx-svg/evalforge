from __future__ import annotations

import pytest

from evalforge_api.domain.test_case_content import (
    MAX_METADATA_BYTES,
    MAX_TAG_LENGTH,
    MAX_TAGS,
    InvalidTestCaseContentError,
    TestCaseContent,
)


def test_minimal_text_input_is_valid() -> None:
    content = TestCaseContent(input="What is 2 + 2?")
    assert content.input == "What is 2 + 2?"
    assert content.tags == ()
    assert content.metadata == {}


def test_structured_input_is_valid() -> None:
    content = TestCaseContent(input={"question": "2 + 2", "locale": "en-US"})
    assert content.input == {"question": "2 + 2", "locale": "en-US"}


def test_full_content_round_trips_through_json() -> None:
    original = TestCaseContent(
        input={"question": "Summarize the policy"},
        expected_output="A two-sentence summary.",
        structured_expected_output={"sentences": 2},
        context_references=("doc://policy/1", "doc://policy/2"),
        tags=("regression", "summarization"),
        metadata={"owner": "quality"},
        difficulty="hard",
        category="summarization",
        safety_labels=("pii-free",),
        tool_expectations=({"tool": "search", "calls": 1},),
        trajectory_expectations=({"step": "retrieve"},),
    )
    restored = TestCaseContent.from_json_dict(original.to_json_dict())
    assert restored == original


def test_to_json_dict_emits_every_field_even_when_unset() -> None:
    payload = TestCaseContent(input="x").to_json_dict()
    assert set(payload) == {
        "input",
        "expected_output",
        "structured_expected_output",
        "context_references",
        "tags",
        "metadata",
        "difficulty",
        "category",
        "safety_labels",
        "tool_expectations",
        "trajectory_expectations",
    }


def test_unknown_top_level_keys_are_ignored_rather_than_rejected() -> None:
    """Content authored before this schema existed stays readable."""
    content = TestCaseContent.from_json_dict({"input": "1 + 1", "expected": "2"})
    assert content.input == "1 + 1"


def test_missing_input_is_rejected() -> None:
    with pytest.raises(InvalidTestCaseContentError):
        TestCaseContent.from_json_dict({"expected_output": "2"})


@pytest.mark.parametrize("empty_input", ["", "   ", "\n\t", {}])
def test_empty_input_is_rejected(empty_input: object) -> None:
    with pytest.raises(InvalidTestCaseContentError):
        TestCaseContent(input=empty_input)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_input", [None, 42, ["a"], True])
def test_non_string_non_object_input_is_rejected(bad_input: object) -> None:
    with pytest.raises(InvalidTestCaseContentError):
        TestCaseContent(input=bad_input)  # type: ignore[arg-type]


def test_too_many_tags_is_rejected() -> None:
    with pytest.raises(InvalidTestCaseContentError):
        TestCaseContent(input="x", tags=tuple(f"tag-{index}" for index in range(MAX_TAGS + 1)))


def test_exactly_the_maximum_number_of_tags_is_allowed() -> None:
    content = TestCaseContent(input="x", tags=tuple(f"tag-{index}" for index in range(MAX_TAGS)))
    assert len(content.tags) == MAX_TAGS


def test_overlong_tag_is_rejected() -> None:
    with pytest.raises(InvalidTestCaseContentError):
        TestCaseContent(input="x", tags=("t" * (MAX_TAG_LENGTH + 1),))


def test_blank_tag_is_rejected() -> None:
    with pytest.raises(InvalidTestCaseContentError):
        TestCaseContent(input="x", tags=("  ",))


def test_oversized_metadata_is_rejected() -> None:
    with pytest.raises(InvalidTestCaseContentError) as excinfo:
        TestCaseContent(input="x", metadata={"blob": "y" * (MAX_METADATA_BYTES + 100)})
    assert "metadata" in str(excinfo.value)


def test_metadata_at_the_bound_is_allowed() -> None:
    # Canonical JSON of {"blob": "y"*N} costs 12 bytes of framing.
    content = TestCaseContent(input="x", metadata={"blob": "y" * (MAX_METADATA_BYTES - 12)})
    assert content.metadata


def test_non_json_serializable_metadata_is_rejected() -> None:
    with pytest.raises(InvalidTestCaseContentError):
        TestCaseContent(input="x", metadata={"when": object()})


def test_non_object_expectation_entry_is_rejected() -> None:
    with pytest.raises(InvalidTestCaseContentError):
        TestCaseContent(input="x", tool_expectations=("not-an-object",))  # type: ignore[arg-type]


def test_blank_category_is_rejected_but_absent_category_is_fine() -> None:
    assert TestCaseContent(input="x", category=None).category is None
    with pytest.raises(InvalidTestCaseContentError):
        TestCaseContent(input="x", category="   ")


def test_tags_supplied_as_a_bare_string_is_rejected() -> None:
    with pytest.raises(InvalidTestCaseContentError):
        TestCaseContent.from_json_dict({"input": "x", "tags": "not-a-list"})
