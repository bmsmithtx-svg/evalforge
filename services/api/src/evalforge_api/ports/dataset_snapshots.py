"""Ports for immutable dataset snapshots and their frozen membership.

Split out of ``evalforge_api.ports.datasets`` so the dataset/test-case
authoring surface and the snapshot surface each stay well inside the
file-size ceiling in docs/MODULARITY_STANDARD.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from evalforge_api.domain.evaluation_enums import DatasetSnapshotStatus, RetentionClass


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


class DatasetSnapshotRepository(Protocol):
    async def create_draft(
        self, *, tenant_id: UUID, dataset_id: UUID, created_by: UUID
    ) -> DatasetSnapshotRecord: ...

    async def get_snapshot(
        self, *, tenant_id: UUID, snapshot_id: UUID
    ) -> DatasetSnapshotRecord | None: ...

    async def list_snapshots(
        self, *, tenant_id: UUID, dataset_id: UUID
    ) -> tuple[DatasetSnapshotRecord, ...]: ...

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
