"""PostgreSQL-backed test-case version queries.

The version half of the ``DatasetRepository`` port: immutable content
versions, the "latest version of each active test case" projections
duplicate detection and export depend on, and the single-transaction
bulk seed used by the import and clone paths.

``PostgresDatasetRepository`` extends this class so the port is
satisfied by one object while each module stays inside the file-size
ceiling in docs/MODULARITY_STANDARD.md. ``test_case_versions`` has no
UPDATE grant: every method here is INSERT or SELECT only.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import asyncpg

from evalforge_api.adapters.dataset_row_mapping import (
    TEST_CASE_COLUMNS,
    TEST_CASE_VERSION_COLUMNS,
    dedup_pair,
    row_to_test_case_version,
)
from evalforge_api.adapters.rls_session import set_tenant_session
from evalforge_api.ports.datasets import TestCaseSeedRow, TestCaseVersionRecord

# "The current content of every active test case in a dataset": one row
# per test case, its highest version number. DISTINCT ON keeps this a
# single index-ordered scan rather than a correlated subquery per case.
# The column list is spelled out rather than interpolated so this stays
# a plain constant statement with no string construction at all.
_LATEST_VERSIONS_SQL = """
SELECT DISTINCT ON (tcv.test_case_id)
    tcv.id, tcv.tenant_id, tcv.test_case_id, tcv.version_number, tcv.content,
    tcv.content_hash, tcv.dedup_hash, tcv.hash_algorithm, tcv.canonicalization_version,
    tcv.retention_class, tcv.retain_until, tcv.archived_at, tcv.created_by, tcv.created_at
FROM test_case_versions tcv
JOIN test_cases tc ON tc.id = tcv.test_case_id AND tc.tenant_id = tcv.tenant_id
WHERE tc.dataset_id = $1 AND tcv.tenant_id = $2 AND tc.status = 'active'
ORDER BY tcv.test_case_id, tcv.version_number DESC
"""


class PostgresTestCaseVersionRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

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
    ) -> TestCaseVersionRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                INSERT INTO test_case_versions (
                    tenant_id, test_case_id, version_number, content, content_hash, dedup_hash,
                    hash_algorithm, canonicalization_version, created_by
                )
                VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9)
                RETURNING {TEST_CASE_VERSION_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                test_case_id,
                version_number,
                json.dumps(content),
                content_hash,
                dedup_hash,
                hash_algorithm,
                canonicalization_version,
                created_by,
            )
        assert row is not None
        return row_to_test_case_version(row)

    async def get_test_case_version(
        self, *, tenant_id: UUID, version_id: UUID
    ) -> TestCaseVersionRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                SELECT {TEST_CASE_VERSION_COLUMNS} FROM test_case_versions
                WHERE id = $1 AND tenant_id = $2
                """,  # noqa: S608
                version_id,
                tenant_id,
            )
        return row_to_test_case_version(row) if row is not None else None

    async def list_test_case_versions(
        self, *, tenant_id: UUID, test_case_id: UUID
    ) -> tuple[TestCaseVersionRecord, ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            rows = await connection.fetch(
                f"""
                SELECT {TEST_CASE_VERSION_COLUMNS} FROM test_case_versions
                WHERE test_case_id = $1 AND tenant_id = $2
                ORDER BY version_number
                """,  # noqa: S608
                test_case_id,
                tenant_id,
            )
        return tuple(row_to_test_case_version(row) for row in rows)

    async def get_latest_test_case_version(
        self, *, tenant_id: UUID, test_case_id: UUID
    ) -> TestCaseVersionRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                SELECT {TEST_CASE_VERSION_COLUMNS} FROM test_case_versions
                WHERE test_case_id = $1 AND tenant_id = $2
                ORDER BY version_number DESC
                LIMIT 1
                """,  # noqa: S608
                test_case_id,
                tenant_id,
            )
        return row_to_test_case_version(row) if row is not None else None

    async def list_latest_versions_for_dataset(
        self, *, tenant_id: UUID, dataset_id: UUID
    ) -> tuple[TestCaseVersionRecord, ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            rows = await connection.fetch(_LATEST_VERSIONS_SQL, dataset_id, tenant_id)
        return tuple(
            sorted(
                (row_to_test_case_version(row) for row in rows), key=lambda v: str(v.test_case_id)
            )
        )

    async def list_current_dedup_hashes(
        self, *, tenant_id: UUID, dataset_id: UUID
    ) -> tuple[tuple[UUID, str], ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            rows = await connection.fetch(
                """
                SELECT DISTINCT ON (tcv.test_case_id) tcv.test_case_id, tcv.dedup_hash
                FROM test_case_versions tcv
                JOIN test_cases tc ON tc.id = tcv.test_case_id AND tc.tenant_id = tcv.tenant_id
                WHERE tc.dataset_id = $1 AND tcv.tenant_id = $2 AND tc.status = 'active'
                ORDER BY tcv.test_case_id, tcv.version_number DESC
                """,
                dataset_id,
                tenant_id,
            )
        return tuple(dedup_pair(row) for row in rows)

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
    ) -> tuple[TestCaseVersionRecord, ...]:
        """Insert every test case and its first version in ONE
        transaction, so a bulk import or clone is all-or-nothing."""
        created: list[TestCaseVersionRecord] = []
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            for seed in rows:
                case_row = await connection.fetchrow(
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
                    seed.external_key,
                    source,
                    seed.source_test_case_id,
                    import_batch_id,
                    created_by,
                )
                assert case_row is not None
                version_row = await connection.fetchrow(
                    f"""
                    INSERT INTO test_case_versions (
                        tenant_id, test_case_id, version_number, content, content_hash,
                        dedup_hash, hash_algorithm, canonicalization_version, created_by
                    )
                    VALUES ($1, $2, 1, $3::jsonb, $4, $5, $6, $7, $8)
                    RETURNING {TEST_CASE_VERSION_COLUMNS}
                    """,  # noqa: S608
                    tenant_id,
                    case_row["id"],
                    json.dumps(seed.content),
                    seed.content_hash,
                    seed.dedup_hash,
                    hash_algorithm,
                    canonicalization_version,
                    created_by,
                )
                assert version_row is not None
                created.append(row_to_test_case_version(version_row))
        return tuple(created)
