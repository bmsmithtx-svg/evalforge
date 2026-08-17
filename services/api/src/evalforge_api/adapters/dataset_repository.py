"""PostgreSQL-backed dataset and test-case repository.

The dataset/test-case half of the ``DatasetRepository`` port; the
version half lives in ``adapters/test_case_version_repository.py`` and
is inherited here so a single object satisfies the whole port.

Mutability boundary: ``datasets`` and ``test_cases`` hold *mutable*
attributes (name, description, tags, metadata, status, archival), so
this adapter issues plain tenant-scoped UPDATEs against them. No
trigger guards those tables because nothing on them is evidence —
evidence lives in ``test_case_versions`` (append-only) and finalized
``dataset_snapshots`` (trigger-protected).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from evalforge_api.adapters.dataset_row_mapping import (
    DATASET_COLUMNS,
    TEST_CASE_COLUMNS,
    row_to_dataset,
    row_to_test_case,
)
from evalforge_api.adapters.rls_session import set_tenant_session
from evalforge_api.adapters.test_case_version_repository import PostgresTestCaseVersionRepository
from evalforge_api.domain.evaluation_enums import DatasetStatus, TestCaseStatus
from evalforge_api.ports.datasets import DatasetRecord, TestCaseRecord


class PostgresDatasetRepository(PostgresTestCaseVersionRepository):
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
    ) -> DatasetRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                INSERT INTO datasets (
                    tenant_id, workspace_id, name, description, tags, metadata, source,
                    cloned_from_dataset_id, cloned_from_snapshot_id, created_by
                )
                VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8, $9, $10)
                RETURNING {DATASET_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                workspace_id,
                name,
                description,
                json.dumps(list(tags)),
                json.dumps(metadata),
                source,
                cloned_from_dataset_id,
                cloned_from_snapshot_id,
                created_by,
            )
        assert row is not None
        return row_to_dataset(row)

    async def get_dataset(self, *, tenant_id: UUID, dataset_id: UUID) -> DatasetRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"SELECT {DATASET_COLUMNS} FROM datasets WHERE id = $1 AND tenant_id = $2",  # noqa: S608
                dataset_id,
                tenant_id,
            )
        return row_to_dataset(row) if row is not None else None

    async def list_datasets(
        self, *, tenant_id: UUID, workspace_id: UUID | None, status: DatasetStatus | None
    ) -> tuple[DatasetRecord, ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            rows = await connection.fetch(
                f"""
                SELECT {DATASET_COLUMNS} FROM datasets
                WHERE tenant_id = $1
                  AND ($2::uuid IS NULL OR workspace_id = $2)
                  AND ($3::text IS NULL OR status = $3::dataset_status)
                ORDER BY created_at, id
                """,  # noqa: S608
                tenant_id,
                workspace_id,
                status.value if status is not None else None,
            )
        return tuple(row_to_dataset(row) for row in rows)

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
    ) -> DatasetRecord | None:
        """Partial update: a ``None`` argument leaves the column as it
        is. ``description`` is cleared by passing an empty string."""
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                UPDATE datasets SET
                    name = COALESCE($3, name),
                    description = COALESCE($4, description),
                    tags = COALESCE($5::jsonb, tags),
                    metadata = COALESCE($6::jsonb, metadata),
                    updated_by = $7,
                    updated_at = now()
                WHERE id = $1 AND tenant_id = $2
                RETURNING {DATASET_COLUMNS}
                """,  # noqa: S608
                dataset_id,
                tenant_id,
                name,
                description,
                json.dumps(list(tags)) if tags is not None else None,
                json.dumps(metadata) if metadata is not None else None,
                updated_by,
            )
        return row_to_dataset(row) if row is not None else None

    async def archive_dataset(
        self, *, tenant_id: UUID, dataset_id: UUID, updated_by: UUID
    ) -> DatasetRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                UPDATE datasets
                SET status = 'archived', archived_at = COALESCE(archived_at, now()),
                    updated_by = $3, updated_at = now()
                WHERE id = $1 AND tenant_id = $2
                RETURNING {DATASET_COLUMNS}
                """,  # noqa: S608
                dataset_id,
                tenant_id,
                updated_by,
            )
        return row_to_dataset(row) if row is not None else None

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
    ) -> TestCaseRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                INSERT INTO test_cases (
                    tenant_id, dataset_id, external_key, source, source_test_case_id,
                    import_batch_id, created_by
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING {TEST_CASE_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                dataset_id,
                external_key,
                source,
                source_test_case_id,
                import_batch_id,
                created_by,
            )
        assert row is not None
        return row_to_test_case(row)

    async def get_test_case(self, *, tenant_id: UUID, test_case_id: UUID) -> TestCaseRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"SELECT {TEST_CASE_COLUMNS} FROM test_cases WHERE id = $1 AND tenant_id = $2",  # noqa: S608
                test_case_id,
                tenant_id,
            )
        return row_to_test_case(row) if row is not None else None

    async def list_test_cases(
        self, *, tenant_id: UUID, dataset_id: UUID, status: TestCaseStatus | None
    ) -> tuple[TestCaseRecord, ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            rows = await connection.fetch(
                f"""
                SELECT {TEST_CASE_COLUMNS} FROM test_cases
                WHERE dataset_id = $1 AND tenant_id = $2
                  AND ($3::text IS NULL OR status = $3::test_case_status)
                ORDER BY created_at, id
                """,  # noqa: S608
                dataset_id,
                tenant_id,
                status.value if status is not None else None,
            )
        return tuple(row_to_test_case(row) for row in rows)

    async def archive_test_case(
        self, *, tenant_id: UUID, test_case_id: UUID, updated_by: UUID
    ) -> TestCaseRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                UPDATE test_cases
                SET status = 'archived', archived_at = COALESCE(archived_at, now()),
                    updated_by = $3, updated_at = now()
                WHERE id = $1 AND tenant_id = $2
                RETURNING {TEST_CASE_COLUMNS}
                """,  # noqa: S608
                test_case_id,
                tenant_id,
                updated_by,
            )
        return row_to_test_case(row) if row is not None else None
