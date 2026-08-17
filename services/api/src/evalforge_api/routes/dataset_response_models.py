"""Pydantic response models for the dataset-management endpoints.

Shared by every ``routes/dataset*`` and ``routes/test_cases`` module so
one record shape has exactly one wire representation, and so each route
module stays well inside the file-size ceiling. Pydantic lives only
here at the delivery boundary — the domain and ports layers use frozen
dataclasses (docs/MODULARITY_STANDARD.md).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from evalforge_api.ports.dataset_snapshots import (
    DatasetSnapshotItemRecord,
    DatasetSnapshotRecord,
)
from evalforge_api.ports.datasets import DatasetRecord, TestCaseRecord, TestCaseVersionRecord


class DatasetResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    tags: list[str]
    metadata: dict[str, Any]
    status: str
    source: str
    cloned_from_dataset_id: UUID | None
    cloned_from_snapshot_id: UUID | None
    archived_at: datetime | None
    created_by: UUID
    created_at: datetime
    updated_by: UUID | None
    updated_at: datetime

    @classmethod
    def from_record(cls, dataset: DatasetRecord) -> DatasetResponse:
        return cls(
            id=dataset.id,
            tenant_id=dataset.tenant_id,
            workspace_id=dataset.workspace_id,
            name=dataset.name,
            description=dataset.description,
            tags=list(dataset.tags),
            metadata=dataset.metadata,
            status=dataset.status.value,
            source=dataset.source,
            cloned_from_dataset_id=dataset.cloned_from_dataset_id,
            cloned_from_snapshot_id=dataset.cloned_from_snapshot_id,
            archived_at=dataset.archived_at,
            created_by=dataset.created_by,
            created_at=dataset.created_at,
            updated_by=dataset.updated_by,
            updated_at=dataset.updated_at,
        )


class TestCaseResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    dataset_id: UUID
    external_key: str | None
    status: str
    source: str
    source_test_case_id: UUID | None
    import_batch_id: UUID | None
    archived_at: datetime | None
    created_by: UUID
    created_at: datetime
    updated_by: UUID | None
    updated_at: datetime

    @classmethod
    def from_record(cls, test_case: TestCaseRecord) -> TestCaseResponse:
        return cls(
            id=test_case.id,
            tenant_id=test_case.tenant_id,
            dataset_id=test_case.dataset_id,
            external_key=test_case.external_key,
            status=test_case.status.value,
            source=test_case.source,
            source_test_case_id=test_case.source_test_case_id,
            import_batch_id=test_case.import_batch_id,
            archived_at=test_case.archived_at,
            created_by=test_case.created_by,
            created_at=test_case.created_at,
            updated_by=test_case.updated_by,
            updated_at=test_case.updated_at,
        )


class TestCaseVersionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    test_case_id: UUID
    version_number: int
    content: dict[str, Any]
    content_hash: str
    dedup_hash: str
    hash_algorithm: str
    canonicalization_version: str
    created_by: UUID
    created_at: datetime

    @classmethod
    def from_record(cls, version: TestCaseVersionRecord) -> TestCaseVersionResponse:
        return cls(
            id=version.id,
            tenant_id=version.tenant_id,
            test_case_id=version.test_case_id,
            version_number=version.version_number,
            content=version.content,
            content_hash=version.content_hash,
            dedup_hash=version.dedup_hash,
            hash_algorithm=version.hash_algorithm,
            canonicalization_version=version.canonicalization_version,
            created_by=version.created_by,
            created_at=version.created_at,
        )


class DatasetSnapshotResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    dataset_id: UUID
    status: str
    content_hash: str | None
    hash_algorithm: str | None
    canonicalization_version: str | None
    item_count: int
    created_by: UUID
    created_at: datetime
    finalized_by: UUID | None
    finalized_at: datetime | None

    @classmethod
    def from_record(cls, snapshot: DatasetSnapshotRecord) -> DatasetSnapshotResponse:
        return cls(
            id=snapshot.id,
            tenant_id=snapshot.tenant_id,
            dataset_id=snapshot.dataset_id,
            status=snapshot.status.value,
            content_hash=snapshot.content_hash,
            hash_algorithm=snapshot.hash_algorithm,
            canonicalization_version=snapshot.canonicalization_version,
            item_count=snapshot.item_count,
            created_by=snapshot.created_by,
            created_at=snapshot.created_at,
            finalized_by=snapshot.finalized_by,
            finalized_at=snapshot.finalized_at,
        )


class DatasetSnapshotItemResponse(BaseModel):
    id: UUID
    snapshot_id: UUID
    test_case_version_id: UUID
    sequence_index: int

    @classmethod
    def from_record(cls, item: DatasetSnapshotItemRecord) -> DatasetSnapshotItemResponse:
        return cls(
            id=item.id,
            snapshot_id=item.snapshot_id,
            test_case_version_id=item.test_case_version_id,
            sequence_index=item.sequence_index,
        )
