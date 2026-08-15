"""PostgreSQL-backed dataset, test-case, and test-case-version repository."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import asyncpg

from evalforge_api.adapters.rls_session import set_tenant_session
from evalforge_api.domain.evaluation_enums import DatasetStatus, RetentionClass, TestCaseStatus
from evalforge_api.ports.datasets import DatasetRecord, TestCaseRecord, TestCaseVersionRecord

_DATASET_COLUMNS = "id, tenant_id, workspace_id, name, status, created_by, created_at"
_TEST_CASE_COLUMNS = "id, tenant_id, dataset_id, external_key, status, created_by, created_at"
_TEST_CASE_VERSION_COLUMNS = (
    "id, tenant_id, test_case_id, version_number, content, content_hash, hash_algorithm, "
    "canonicalization_version, retention_class, retain_until, archived_at, created_by, created_at"
)


def _row_to_dataset(row: asyncpg.Record) -> DatasetRecord:
    return DatasetRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        workspace_id=row["workspace_id"],
        name=row["name"],
        status=DatasetStatus(row["status"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def _row_to_test_case(row: asyncpg.Record) -> TestCaseRecord:
    return TestCaseRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        dataset_id=row["dataset_id"],
        external_key=row["external_key"],
        status=TestCaseStatus(row["status"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def _row_to_test_case_version(row: asyncpg.Record) -> TestCaseVersionRecord:
    return TestCaseVersionRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        test_case_id=row["test_case_id"],
        version_number=row["version_number"],
        content=json.loads(row["content"]),
        content_hash=row["content_hash"],
        hash_algorithm=row["hash_algorithm"],
        canonicalization_version=row["canonicalization_version"],
        retention_class=RetentionClass(row["retention_class"]),
        retain_until=row["retain_until"],
        archived_at=row["archived_at"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


class PostgresDatasetRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_dataset(
        self, *, tenant_id: UUID, workspace_id: UUID, name: str, created_by: UUID
    ) -> DatasetRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                INSERT INTO datasets (tenant_id, workspace_id, name, created_by)
                VALUES ($1, $2, $3, $4)
                RETURNING {_DATASET_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                workspace_id,
                name,
                created_by,
            )
        assert row is not None
        return _row_to_dataset(row)

    async def get_dataset(self, *, tenant_id: UUID, dataset_id: UUID) -> DatasetRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"SELECT {_DATASET_COLUMNS} FROM datasets WHERE id = $1 AND tenant_id = $2",  # noqa: S608
                dataset_id,
                tenant_id,
            )
        return _row_to_dataset(row) if row is not None else None

    async def create_test_case(
        self,
        *,
        tenant_id: UUID,
        dataset_id: UUID,
        external_key: str | None,
        created_by: UUID,
    ) -> TestCaseRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                INSERT INTO test_cases (tenant_id, dataset_id, external_key, created_by)
                VALUES ($1, $2, $3, $4)
                RETURNING {_TEST_CASE_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                dataset_id,
                external_key,
                created_by,
            )
        assert row is not None
        return _row_to_test_case(row)

    async def get_test_case(self, *, tenant_id: UUID, test_case_id: UUID) -> TestCaseRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"SELECT {_TEST_CASE_COLUMNS} FROM test_cases WHERE id = $1 AND tenant_id = $2",  # noqa: S608
                test_case_id,
                tenant_id,
            )
        return _row_to_test_case(row) if row is not None else None

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
    ) -> TestCaseVersionRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                INSERT INTO test_case_versions (
                    tenant_id, test_case_id, version_number, content, content_hash,
                    hash_algorithm, canonicalization_version, created_by
                )
                VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8)
                RETURNING {_TEST_CASE_VERSION_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                test_case_id,
                version_number,
                json.dumps(content),
                content_hash,
                hash_algorithm,
                canonicalization_version,
                created_by,
            )
        assert row is not None
        return _row_to_test_case_version(row)

    async def get_test_case_version(
        self, *, tenant_id: UUID, version_id: UUID
    ) -> TestCaseVersionRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                SELECT {_TEST_CASE_VERSION_COLUMNS} FROM test_case_versions
                WHERE id = $1 AND tenant_id = $2
                """,  # noqa: S608
                version_id,
                tenant_id,
            )
        return _row_to_test_case_version(row) if row is not None else None

    async def list_test_case_versions(
        self, *, tenant_id: UUID, test_case_id: UUID
    ) -> tuple[TestCaseVersionRecord, ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            rows = await connection.fetch(
                f"""
                SELECT {_TEST_CASE_VERSION_COLUMNS} FROM test_case_versions
                WHERE test_case_id = $1 AND tenant_id = $2
                ORDER BY version_number
                """,  # noqa: S608
                test_case_id,
                tenant_id,
            )
        return tuple(_row_to_test_case_version(row) for row in rows)
