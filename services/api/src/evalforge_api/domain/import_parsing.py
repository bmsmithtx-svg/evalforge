"""Pure parsing and validation of dataset import payloads.

No database access, no I/O: this module turns a CSV or JSONL document
into either a validated :class:`~evalforge_api.domain.test_case_content.TestCaseContent`
or a per-row error message. ``evalforge_api.application.dataset_import_service``
decides what to persist.

Only the standard library ``csv`` and ``json`` modules are used. Import
payloads are untrusted tenant input, so nothing here evaluates,
executes, or unpickles any part of the document
(docs/THREAT_MODEL.md).

A malformed row is a *result*, never an exception: parsing always
returns one :class:`ParsedImportRow` per input row, with ``error`` set
and ``content`` ``None`` for rows that failed, so the caller can report
exactly which row failed and why.

CSV schema (header row required; unknown columns are ignored, and the
same columns are what ``domain/export_formatting`` emits, so an export
round-trips through an import):

===================  ==========================================================
``input``            required; the test-case input text
``expected_output``  optional; blank means "no expected output"
``tags``             optional; comma-separated, e.g. ``"safety,regression"``
``category``         optional
``difficulty``       optional
``metadata``         optional; a JSON object encoded as a string
``external_key``     optional; the caller's own stable key for the test case
===================  ==========================================================

JSONL schema: one JSON object per line, whose keys are the
``TestCaseContent`` field names, plus an optional ``external_key``.
Blank lines are skipped and do not consume a row index.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from typing import Any

from evalforge_api.domain.test_case_content import InvalidTestCaseContentError, TestCaseContent

CSV_COLUMNS: tuple[str, ...] = (
    "external_key",
    "input",
    "expected_output",
    "tags",
    "category",
    "difficulty",
    "metadata",
)

MAX_IMPORT_ROWS = 5_000
MAX_EXTERNAL_KEY_LENGTH = 200


class ImportPayloadTooLargeError(Exception):
    """Raised when an import document exceeds the supported row count."""


@dataclass(frozen=True, slots=True)
class ParsedImportRow:
    row_index: int
    external_key: str | None
    content: TestCaseContent | None
    error: str | None


def _failed(row_index: int, external_key: str | None, message: str) -> ParsedImportRow:
    return ParsedImportRow(
        row_index=row_index, external_key=external_key, content=None, error=message
    )


def _clean_external_key(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > MAX_EXTERNAL_KEY_LENGTH:
        raise InvalidTestCaseContentError(
            f"external_key must be at most {MAX_EXTERNAL_KEY_LENGTH} characters."
        )
    return text


def _split_tags(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _content_from_csv_row(row: dict[str, str | None]) -> TestCaseContent:
    metadata_text = _blank_to_none(row.get("metadata"))
    if metadata_text is None:
        metadata: dict[str, Any] = {}
    else:
        try:
            decoded = json.loads(metadata_text)
        except json.JSONDecodeError as exc:
            raise InvalidTestCaseContentError(f"metadata is not valid JSON: {exc.msg}") from exc
        if not isinstance(decoded, dict):
            raise InvalidTestCaseContentError("metadata must decode to a JSON object.")
        metadata = decoded
    return TestCaseContent(
        input=row.get("input") or "",
        expected_output=_blank_to_none(row.get("expected_output")),
        tags=_split_tags(_blank_to_none(row.get("tags"))),
        category=_blank_to_none(row.get("category")),
        difficulty=_blank_to_none(row.get("difficulty")),
        metadata=metadata,
    )


def parse_csv(document: str) -> tuple[ParsedImportRow, ...]:
    """Parse a CSV import document into one result per data row."""
    reader = csv.DictReader(io.StringIO(document))
    if reader.fieldnames is None:
        return ()
    if "input" not in reader.fieldnames:
        return (_failed(1, None, "CSV header must include an 'input' column."),)

    rows: list[ParsedImportRow] = []
    for row_index, raw in enumerate(reader, start=1):
        _guard_row_count(row_index)
        external_key: str | None = None
        try:
            external_key = _clean_external_key(raw.get("external_key"))
            content = _content_from_csv_row(raw)
        except InvalidTestCaseContentError as exc:
            rows.append(_failed(row_index, external_key, str(exc)))
            continue
        rows.append(
            ParsedImportRow(
                row_index=row_index, external_key=external_key, content=content, error=None
            )
        )
    return tuple(rows)


def parse_jsonl(document: str) -> tuple[ParsedImportRow, ...]:
    """Parse a JSONL import document into one result per non-blank line."""
    rows: list[ParsedImportRow] = []
    row_index = 0
    for line in document.splitlines():
        if not line.strip():
            continue
        row_index += 1
        _guard_row_count(row_index)
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError as exc:
            rows.append(_failed(row_index, None, f"Line is not valid JSON: {exc.msg}"))
            continue
        if not isinstance(decoded, dict):
            rows.append(_failed(row_index, None, "Each JSONL line must be a JSON object."))
            continue
        external_key: str | None = None
        try:
            external_key = _clean_external_key(decoded.get("external_key"))
            content = TestCaseContent.from_json_dict(decoded)
        except InvalidTestCaseContentError as exc:
            rows.append(_failed(row_index, external_key, str(exc)))
            continue
        rows.append(
            ParsedImportRow(
                row_index=row_index, external_key=external_key, content=content, error=None
            )
        )
    return tuple(rows)


def _guard_row_count(row_index: int) -> None:
    if row_index > MAX_IMPORT_ROWS:
        raise ImportPayloadTooLargeError(f"An import may contain at most {MAX_IMPORT_ROWS} rows.")
