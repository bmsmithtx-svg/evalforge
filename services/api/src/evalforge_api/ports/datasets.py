"""Ports for datasets, test cases, and immutable dataset snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from evalforge_api.domain.evaluation_enums import (
    DatasetSnapshotStatus,
    DatasetStatus,
    RetentionClass,
    TestCaseStatus,
)


@dataclass(frozen=True, slots=True)
class DatasetRecord:
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    name: str
    status: DatasetStatus
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TestCaseRecord:
    id: UUID
    tenant_id: UUID
    dataset_id: UUID
    external_key: str | None
    status: TestCaseStatus
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TestCaseVersionRecord:
    id: UUID
    tenant_id: UUID
    test_case_id: UUID
    version_number: int
    content: dict[str, Any]
    content_hash: str
    hash_algorithm: str
    canonicalization_version: str
    retention_class: RetentionClass
    retain_until: datetime | None
    archived_at: datetime | None
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DatasetSnapshotRecord:
    id: UUID
    tenant_id: UUID
    dataset_id: UUID
    status: DatasetSnapshotStatus
    content_hash: str | None
    hash_algorithm: str | None
    canonicalization_version: str | None
    item_count: int
    retention_class: RetentionClass
    retain_until: datetime | None
    archived_at: datetime | None
    created_by: UUID
    created_at: datetime
    finalized_by: UUID | None
    finalized_at: datetime | None


@dataclass(frozen=True, slots=True)
class DatasetSnapshotItemRecord:
    id: UUID
    tenant_id: UUID
    snapshot_id: UUID
    test_case_version_id: UUID
    sequence_index: int
    created_at: datetime


class DatasetRepository(Protocol):
    async def create_dataset(
        self, *, tenant_id: UUID, workspace_id: UUID, name: str, created_by: UUID
    ) -> DatasetRecord: ...

    async def get_dataset(self, *, tenant_id: UUID, dataset_id: UUID) -> DatasetRecord | None: ...

    async def create_test_case(
        self,
        *,
        tenant_id: UUID,
        dataset_id: UUID,
        external_key: str | None,
        created_by: UUID,
    ) -> TestCaseRecord: ...

    async def get_test_case(
        self, *, tenant_id: UUID, test_case_id: UUID
    ) -> TestCaseRecord | None: ...

    async def create_test_case_version(
        self,
        *,
        tenant_id: UUID,
        test_case_id: UUID,
        version_number: int,
        content: dict[str, Any],
        content_hash: str,
        hash_algorithm: str,
        canonicalization_version: str,
        created_by: UUID,
    ) -> TestCaseVersionRecord: ...

    async def get_test_case_version(
        self, *, tenant_id: UUID, version_id: UUID
    ) -> TestCaseVersionRecord | None: ...

    async def list_test_case_versions(
        self, *, tenant_id: UUID, test_case_id: UUID
    ) -> tuple[TestCaseVersionRecord, ...]: ...


class DatasetSnapshotRepository(Protocol):
    async def create_draft(
        self, *, tenant_id: UUID, dataset_id: UUID, created_by: UUID
    ) -> DatasetSnapshotRecord: ...

    async def get_snapshot(
        self, *, tenant_id: UUID, snapshot_id: UUID
    ) -> DatasetSnapshotRecord | None: ...

    async def add_item(
        self,
        *,
        tenant_id: UUID,
        snapshot_id: UUID,
        test_case_version_id: UUID,
        sequence_index: int,
    ) -> DatasetSnapshotItemRecord: ...

    async def list_items(
        self, *, tenant_id: UUID, snapshot_id: UUID
    ) -> tuple[DatasetSnapshotItemRecord, ...]: ...

    async def finalize(
        self,
        *,
        tenant_id: UUID,
        snapshot_id: UUID,
        content_hash: str,
        hash_algorithm: str,
        canonicalization_version: str,
        item_count: int,
        finalized_by: UUID,
    ) -> DatasetSnapshotRecord: ...
