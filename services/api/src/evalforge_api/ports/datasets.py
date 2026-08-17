"""Ports for datasets, test cases, and versioned test-case content.

Immutable dataset snapshots live in
``evalforge_api.ports.dataset_snapshots`` so neither module approaches
the file-size ceiling in docs/MODULARITY_STANDARD.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from evalforge_api.domain.evaluation_enums import DatasetStatus, RetentionClass, TestCaseStatus


@dataclass(frozen=True, slots=True)
class DatasetRecord:
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    tags: tuple[str, ...]
    metadata: dict[str, Any]
    status: DatasetStatus
    source: str
    cloned_from_dataset_id: UUID | None
    cloned_from_snapshot_id: UUID | None
    archived_at: datetime | None
    created_by: UUID
    created_at: datetime
    updated_by: UUID | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TestCaseRecord:
    id: UUID
    tenant_id: UUID
    dataset_id: UUID
    external_key: str | None
    status: TestCaseStatus
    source: str
    source_test_case_id: UUID | None
    import_batch_id: UUID | None
    archived_at: datetime | None
    created_by: UUID
    created_at: datetime
    updated_by: UUID | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TestCaseVersionRecord:
    id: UUID
    tenant_id: UUID
    test_case_id: UUID
    version_number: int
    content: dict[str, Any]
    content_hash: str
    dedup_hash: str
    hash_algorithm: str
    canonicalization_version: str
    retention_class: RetentionClass
    retain_until: datetime | None
    archived_at: datetime | None
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TestCaseSeedRow:
    """One test case plus its first content version, for the bulk
    import and clone paths that must commit atomically."""

    external_key: str | None
    content: dict[str, Any]
    content_hash: str
    dedup_hash: str
    source_test_case_id: UUID | None = None


class DatasetRepository(Protocol):
    async def create_dataset(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        name: str,
        description: str | None,
        tags: Sequence[str],
        metadata: dict[str, Any],
        source: str,
        cloned_from_dataset_id: UUID | None,
        cloned_from_snapshot_id: UUID | None,
        created_by: UUID,
    ) -> DatasetRecord: ...

    async def get_dataset(self, *, tenant_id: UUID, dataset_id: UUID) -> DatasetRecord | None: ...

    async def list_datasets(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID | None,
        status: DatasetStatus | None,
    ) -> tuple[DatasetRecord, ...]: ...

    async def update_dataset(
        self,
        *,
        tenant_id: UUID,
        dataset_id: UUID,
        name: str | None,
        description: str | None,
        tags: Sequence[str] | None,
        metadata: dict[str, Any] | None,
        updated_by: UUID,
    ) -> DatasetRecord | None: ...

    async def archive_dataset(
        self, *, tenant_id: UUID, dataset_id: UUID, updated_by: UUID
    ) -> DatasetRecord | None: ...

    async def create_test_case(
        self,
        *,
        tenant_id: UUID,
        dataset_id: UUID,
        external_key: str | None,
        source: str,
        source_test_case_id: UUID | None,
        import_batch_id: UUID | None,
        created_by: UUID,
    ) -> TestCaseRecord: ...

    async def get_test_case(
        self, *, tenant_id: UUID, test_case_id: UUID
    ) -> TestCaseRecord | None: ...

    async def list_test_cases(
        self, *, tenant_id: UUID, dataset_id: UUID, status: TestCaseStatus | None
    ) -> tuple[TestCaseRecord, ...]: ...

    async def archive_test_case(
        self, *, tenant_id: UUID, test_case_id: UUID, updated_by: UUID
    ) -> TestCaseRecord | None: ...

    async def create_test_case_version(
        self,
        *,
        tenant_id: UUID,
        test_case_id: UUID,
        version_number: int,
        content: dict[str, Any],
        content_hash: str,
        dedup_hash: str,
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

    async def get_latest_test_case_version(
        self, *, tenant_id: UUID, test_case_id: UUID
    ) -> TestCaseVersionRecord | None: ...

    async def list_latest_versions_for_dataset(
        self, *, tenant_id: UUID, dataset_id: UUID
    ) -> tuple[TestCaseVersionRecord, ...]: ...

    async def list_current_dedup_hashes(
        self, *, tenant_id: UUID, dataset_id: UUID
    ) -> tuple[tuple[UUID, str], ...]: ...

    async def create_test_cases_with_versions(
        self,
        *,
        tenant_id: UUID,
        dataset_id: UUID,
        rows: Sequence[TestCaseSeedRow],
        source: str,
        import_batch_id: UUID | None,
        hash_algorithm: str,
        canonicalization_version: str,
        created_by: UUID,
    ) -> tuple[TestCaseVersionRecord, ...]: ...
