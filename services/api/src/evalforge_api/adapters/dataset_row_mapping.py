"""Column lists and row-to-record mapping for the dataset aggregate.

Shared by ``adapters/dataset_repository.py`` and
``adapters/test_case_version_repository.py`` so the two halves of the
``DatasetRepository`` port agree on exactly which columns they select
and how a row becomes a typed record — and so neither module carries a
duplicate copy of the mapping.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import asyncpg

from evalforge_api.domain.evaluation_enums import DatasetStatus, RetentionClass, TestCaseStatus
from evalforge_api.ports.datasets import DatasetRecord, TestCaseRecord, TestCaseVersionRecord

DATASET_COLUMNS = (
    "id, tenant_id, workspace_id, name, description, tags, metadata, status, source, "
    "cloned_from_dataset_id, cloned_from_snapshot_id, archived_at, created_by, created_at, "
    "updated_by, updated_at"
)
TEST_CASE_COLUMNS = (
    "id, tenant_id, dataset_id, external_key, status, source, source_test_case_id, "
    "import_batch_id, archived_at, created_by, created_at, updated_by, updated_at"
)
TEST_CASE_VERSION_COLUMNS = (
    "id, tenant_id, test_case_id, version_number, content, content_hash, dedup_hash, "
    "hash_algorithm, canonicalization_version, retention_class, retain_until, archived_at, "
    "created_by, created_at"
)


def _decode_json(value: Any, fallback: Any) -> Any:
    """asyncpg returns JSONB as a ``str`` unless a codec is registered;
    accept either shape so the mapping does not depend on codec setup."""
    if value is None:
        return fallback
    if isinstance(value, str | bytes):
        return json.loads(value)
    return value


def row_to_dataset(row: asyncpg.Record) -> DatasetRecord:
    tags: list[str] = _decode_json(row["tags"], [])
    metadata: dict[str, Any] = _decode_json(row["metadata"], {})
    return DatasetRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        workspace_id=row["workspace_id"],
        name=row["name"],
        description=row["description"],
        tags=tuple(tags),
        metadata=metadata,
        status=DatasetStatus(row["status"]),
        source=row["source"],
        cloned_from_dataset_id=row["cloned_from_dataset_id"],
        cloned_from_snapshot_id=row["cloned_from_snapshot_id"],
        archived_at=row["archived_at"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_by=row["updated_by"],
        updated_at=row["updated_at"],
    )


def row_to_test_case(row: asyncpg.Record) -> TestCaseRecord:
    return TestCaseRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        dataset_id=row["dataset_id"],
        external_key=row["external_key"],
        status=TestCaseStatus(row["status"]),
        source=row["source"],
        source_test_case_id=row["source_test_case_id"],
        import_batch_id=row["import_batch_id"],
        archived_at=row["archived_at"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_by=row["updated_by"],
        updated_at=row["updated_at"],
    )


def row_to_test_case_version(row: asyncpg.Record) -> TestCaseVersionRecord:
    return TestCaseVersionRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        test_case_id=row["test_case_id"],
        version_number=row["version_number"],
        content=_decode_json(row["content"], {}),
        content_hash=row["content_hash"],
        dedup_hash=row["dedup_hash"],
        hash_algorithm=row["hash_algorithm"],
        canonicalization_version=row["canonicalization_version"],
        retention_class=RetentionClass(row["retention_class"]),
        retain_until=row["retain_until"],
        archived_at=row["archived_at"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def dedup_pair(row: asyncpg.Record) -> tuple[UUID, str]:
    test_case_id: UUID = row["test_case_id"]
    return (test_case_id, row["dedup_hash"])
