"""Typed, validated test-case content.

Milestone 4 stored test-case content as an unstructured ``dict`` in the
``test_case_versions.content`` JSONB column. Milestone 6 gives that
content an explicit domain schema so authoring, import, export,
duplicate detection, and (later) evaluation all agree on what a test
case *is*, without moving persistence concerns into the domain: the
database column stays plain JSON and this module is the only place
that knows how to read and write it.

Pure domain policy — no pydantic, no FastAPI, no asyncpg (see
docs/MODULARITY_STANDARD.md, "Domain packages must not import delivery
or infrastructure packages"; pydantic is used only at the delivery
boundary in ``evalforge_api.routes``).

Bounds follow the same style as ``evalforge_api.domain.ingestion``:
explicit named constants, checked against the canonical-JSON byte size
so the limit does not depend on incidental serialization behavior.
Unknown top-level keys are ignored by :meth:`TestCaseContent.from_json_dict`
rather than rejected — stored content authored before this schema
existed stays readable, and the authoring path persists the caller's
original JSON verbatim so no key is ever silently dropped from storage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evalforge_api.domain.hashing import canonicalize_json

MAX_TAGS = 50
MAX_TAG_LENGTH = 100
MAX_CONTEXT_REFERENCES = 100
MAX_CONTEXT_REFERENCE_LENGTH = 500
MAX_SAFETY_LABELS = 50
MAX_EXPECTATION_ENTRIES = 50
MAX_SHORT_LABEL_LENGTH = 100
MAX_INPUT_BYTES = 64_000
MAX_EXPECTED_OUTPUT_BYTES = 64_000
MAX_METADATA_BYTES = 16_000
MAX_EXPECTATIONS_BYTES = 32_000


class InvalidTestCaseContentError(Exception):
    """Raised when test-case content violates the domain schema."""


def _require_json_safe(value: Any, *, label: str) -> bytes:
    try:
        return canonicalize_json(value)
    except (TypeError, ValueError) as exc:
        raise InvalidTestCaseContentError(f"{label} is not JSON-serializable content.") from exc


def _validate_json_bound(value: Any, *, max_bytes: int, label: str) -> None:
    size = len(_require_json_safe(value, label=label))
    if size > max_bytes:
        raise InvalidTestCaseContentError(
            f"{label} exceeds the {max_bytes}-byte limit ({size} bytes)."
        )


def _validate_string_tuple(
    values: tuple[str, ...], *, max_entries: int, max_length: int, label: str
) -> None:
    if len(values) > max_entries:
        raise InvalidTestCaseContentError(
            f"{label} may contain at most {max_entries} entries (received {len(values)})."
        )
    for entry in values:
        if not isinstance(entry, str):
            raise InvalidTestCaseContentError(f"Every {label} entry must be a string.")
        if not entry.strip():
            raise InvalidTestCaseContentError(f"{label} entries must not be blank.")
        if len(entry) > max_length:
            raise InvalidTestCaseContentError(
                f"Every {label} entry must be at most {max_length} characters."
            )


def _validate_short_label(value: str | None, *, label: str) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise InvalidTestCaseContentError(f"{label} must be a string when present.")
    if not value.strip():
        raise InvalidTestCaseContentError(f"{label} must not be blank when present.")
    if len(value) > MAX_SHORT_LABEL_LENGTH:
        raise InvalidTestCaseContentError(
            f"{label} must be at most {MAX_SHORT_LABEL_LENGTH} characters."
        )


def _validate_input(value: dict[str, Any] | str) -> None:
    if isinstance(value, str):
        if not value.strip():
            raise InvalidTestCaseContentError("Test-case input must not be empty.")
    elif isinstance(value, dict):
        if not value:
            raise InvalidTestCaseContentError("Test-case input must not be empty.")
    else:
        raise InvalidTestCaseContentError(
            "Test-case input must be a non-empty string or a non-empty JSON object."
        )
    _validate_json_bound(value, max_bytes=MAX_INPUT_BYTES, label="Test-case input")


def _validate_expectations(values: tuple[dict[str, Any], ...], *, label: str) -> None:
    if len(values) > MAX_EXPECTATION_ENTRIES:
        raise InvalidTestCaseContentError(
            f"{label} may contain at most {MAX_EXPECTATION_ENTRIES} entries "
            f"(received {len(values)})."
        )
    for entry in values:
        if not isinstance(entry, dict):
            raise InvalidTestCaseContentError(f"Every {label} entry must be a JSON object.")
    _validate_json_bound(list(values), max_bytes=MAX_EXPECTATIONS_BYTES, label=label)


@dataclass(frozen=True, slots=True)
class TestCaseContent:
    """A validated test case. Constructing one is always safe: the
    invariants below are checked in ``__post_init__``, so no invalid
    instance can exist anywhere in the application."""

    input: dict[str, Any] | str
    expected_output: str | None = None
    structured_expected_output: dict[str, Any] | None = None
    context_references: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    difficulty: str | None = None
    category: str | None = None
    safety_labels: tuple[str, ...] = ()
    tool_expectations: tuple[dict[str, Any], ...] = ()
    trajectory_expectations: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        _validate_input(self.input)
        if self.expected_output is not None:
            if not isinstance(self.expected_output, str):
                raise InvalidTestCaseContentError("expected_output must be a string when present.")
            _validate_json_bound(
                self.expected_output, max_bytes=MAX_EXPECTED_OUTPUT_BYTES, label="expected_output"
            )
        if self.structured_expected_output is not None:
            if not isinstance(self.structured_expected_output, dict):
                raise InvalidTestCaseContentError(
                    "structured_expected_output must be a JSON object when present."
                )
            _validate_json_bound(
                self.structured_expected_output,
                max_bytes=MAX_EXPECTED_OUTPUT_BYTES,
                label="structured_expected_output",
            )
        _validate_string_tuple(
            self.context_references,
            max_entries=MAX_CONTEXT_REFERENCES,
            max_length=MAX_CONTEXT_REFERENCE_LENGTH,
            label="context_references",
        )
        _validate_string_tuple(
            self.tags, max_entries=MAX_TAGS, max_length=MAX_TAG_LENGTH, label="tags"
        )
        _validate_string_tuple(
            self.safety_labels,
            max_entries=MAX_SAFETY_LABELS,
            max_length=MAX_TAG_LENGTH,
            label="safety_labels",
        )
        if not isinstance(self.metadata, dict):
            raise InvalidTestCaseContentError("metadata must be a JSON object.")
        _validate_json_bound(self.metadata, max_bytes=MAX_METADATA_BYTES, label="metadata")
        _validate_short_label(self.difficulty, label="difficulty")
        _validate_short_label(self.category, label="category")
        _validate_expectations(self.tool_expectations, label="tool_expectations")
        _validate_expectations(self.trajectory_expectations, label="trajectory_expectations")

    def to_json_dict(self) -> dict[str, Any]:
        """The JSONB representation stored in ``test_case_versions.content``.

        Every field is emitted, including ``None`` and empty
        collections, so two logically identical test cases always
        produce identical canonical JSON regardless of how they were
        authored (docs/REPRODUCIBILITY_CONTRACT.md).
        """
        return {
            "input": self.input,
            "expected_output": self.expected_output,
            "structured_expected_output": self.structured_expected_output,
            "context_references": list(self.context_references),
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "difficulty": self.difficulty,
            "category": self.category,
            "safety_labels": list(self.safety_labels),
            "tool_expectations": [dict(entry) for entry in self.tool_expectations],
            "trajectory_expectations": [dict(entry) for entry in self.trajectory_expectations],
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> TestCaseContent:
        """Read stored (or submitted) JSON into the typed model.

        Unknown top-level keys are ignored; a missing or malformed
        ``input`` is a validation failure.
        """
        if not isinstance(data, dict):
            raise InvalidTestCaseContentError("Test-case content must be a JSON object.")
        if "input" not in data:
            raise InvalidTestCaseContentError("Test-case content must include 'input'.")
        return cls(
            input=data["input"],
            expected_output=data.get("expected_output"),
            structured_expected_output=data.get("structured_expected_output"),
            context_references=_as_string_tuple(
                data.get("context_references"), "context_references"
            ),
            tags=_as_string_tuple(data.get("tags"), "tags"),
            metadata=data.get("metadata") or {},
            difficulty=data.get("difficulty"),
            category=data.get("category"),
            safety_labels=_as_string_tuple(data.get("safety_labels"), "safety_labels"),
            tool_expectations=_as_object_tuple(data.get("tool_expectations"), "tool_expectations"),
            trajectory_expectations=_as_object_tuple(
                data.get("trajectory_expectations"), "trajectory_expectations"
            ),
        )


def _as_string_tuple(value: Any, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, list | tuple):
        raise InvalidTestCaseContentError(f"{label} must be a list of strings.")
    return tuple(value)


def _as_object_tuple(value: Any, label: str) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, list | tuple):
        raise InvalidTestCaseContentError(f"{label} must be a list of JSON objects.")
    return tuple(value)
