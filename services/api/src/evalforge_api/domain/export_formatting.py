"""Pure, deterministic formatting of dataset exports.

No database access: ``evalforge_api.application.dataset_export_service``
loads the rows and this module renders them.

Provenance convention
---------------------
Every export identifies exactly what was exported so a recipient can
verify it against the platform:

* **JSONL** — the *first* line is a header object under the single key
  ``evalforge_export`` carrying ``format_version``, ``dataset_id``,
  ``snapshot_id`` (``null`` for a current-state export),
  ``snapshot_content_hash`` (``null`` likewise), and ``item_count``.
  Every following line is one test case.
* **CSV** — the import columns come first, followed by three
  provenance columns repeated on every row: ``dataset_id``,
  ``snapshot_id``, ``snapshot_content_hash``. Repeating them per row
  keeps the file a plain, tool-readable CSV with no out-of-band
  header, and ``domain/import_parsing`` ignores unknown columns, so an
  exported CSV re-imports unchanged.

Determinism: the caller supplies rows in their final order (snapshot
``sequence_index``, or test-case ID order for a current-state export)
and JSON is emitted with sorted keys and fixed separators, so the same
dataset state always produces byte-identical output.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from uuid import UUID

from evalforge_api.domain.import_parsing import CSV_COLUMNS
from evalforge_api.domain.test_case_content import TestCaseContent

EXPORT_FORMAT_VERSION = "dataset-export-v1"
PROVENANCE_COLUMNS: tuple[str, ...] = ("dataset_id", "snapshot_id", "snapshot_content_hash")
CSV_EXPORT_COLUMNS: tuple[str, ...] = CSV_COLUMNS + PROVENANCE_COLUMNS


@dataclass(frozen=True, slots=True)
class ExportProvenance:
    dataset_id: UUID
    snapshot_id: UUID | None
    snapshot_content_hash: str | None


@dataclass(frozen=True, slots=True)
class ExportRow:
    test_case_id: UUID
    external_key: str | None
    version_id: UUID
    version_number: int
    content_hash: str
    sequence_index: int | None
    content: TestCaseContent


def _header_object(provenance: ExportProvenance, *, item_count: int) -> dict[str, object]:
    return {
        "evalforge_export": {
            "format_version": EXPORT_FORMAT_VERSION,
            "dataset_id": str(provenance.dataset_id),
            "snapshot_id": (
                str(provenance.snapshot_id) if provenance.snapshot_id is not None else None
            ),
            "snapshot_content_hash": provenance.snapshot_content_hash,
            "item_count": item_count,
        }
    }


def format_jsonl(rows: tuple[ExportRow, ...], *, provenance: ExportProvenance) -> str:
    """Render the header line followed by one JSON object per test case."""
    lines = [json.dumps(_header_object(provenance, item_count=len(rows)), sort_keys=True)]
    for row in rows:
        payload: dict[str, object] = {
            "test_case_id": str(row.test_case_id),
            "external_key": row.external_key,
            "test_case_version_id": str(row.version_id),
            "version_number": row.version_number,
            "content_hash": row.content_hash,
            "sequence_index": row.sequence_index,
        }
        payload.update(row.content.to_json_dict())
        lines.append(json.dumps(payload, sort_keys=True))
    return "\n".join(lines) + "\n"


def format_csv(rows: tuple[ExportRow, ...], *, provenance: ExportProvenance) -> str:
    """Render the import column schema plus per-row provenance columns."""
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(CSV_EXPORT_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        content = row.content
        writer.writerow(
            {
                "external_key": row.external_key or "",
                "input": content.input
                if isinstance(content.input, str)
                else json.dumps(content.input, sort_keys=True),
                "expected_output": content.expected_output or "",
                "tags": ",".join(content.tags),
                "category": content.category or "",
                "difficulty": content.difficulty or "",
                "metadata": json.dumps(content.metadata, sort_keys=True)
                if content.metadata
                else "",
                "dataset_id": str(provenance.dataset_id),
                "snapshot_id": (
                    str(provenance.snapshot_id) if provenance.snapshot_id is not None else ""
                ),
                "snapshot_content_hash": provenance.snapshot_content_hash or "",
            }
        )
    return buffer.getvalue()
