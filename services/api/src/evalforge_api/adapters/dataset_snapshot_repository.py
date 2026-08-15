"""PostgreSQL-backed immutable dataset-snapshot repository.

Draft-only membership and post-finalization immutability are enforced
independently by database triggers (see the datasets-and-snapshots
migration); this adapter translates the resulting Postgres
``RAISE EXCEPTION`` into a typed domain exception rather than letting
callers depend on raw driver errors.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

from evalforge_api.adapters.rls_session import set_tenant_session
from evalforge_api.domain.evaluation_enums import DatasetSnapshotStatus, RetentionClass
from evalforge_api.ports.datasets import DatasetSnapshotItemRecord, DatasetSnapshotRecord

_SNAPSHOT_COLUMNS = (
    "id, tenant_id, dataset_id, status, content_hash, hash_algorithm, "
    "canonicalization_version, item_count, retention_class, retain_until, archived_at, "
    "created_by, created_at, finalized_by, finalized_at"
)
_ITEM_COLUMNS = "id, tenant_id, snapshot_id, test_case_version_id, sequence_index, created_at"


class SnapshotNotDraftError(Exception):
    """Raised when a database trigger rejects a mutation because the
    target snapshot is no longer a draft, or an item does not belong
    to the snapshot's own dataset."""


def _row_to_snapshot(row: asyncpg.Record) -> DatasetSnapshotRecord:
    return DatasetSnapshotRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        dataset_id=row["dataset_id"],
        status=DatasetSnapshotStatus(row["status"]),
        content_hash=row["content_hash"],
        hash_algorithm=row["hash_algorithm"],
        canonicalization_version=row["canonicalization_version"],
        item_count=row["item_count"],
        retention_class=RetentionClass(row["retention_class"]),
        retain_until=row["retain_until"],
        archived_at=row["archived_at"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        finalized_by=row["finalized_by"],
        finalized_at=row["finalized_at"],
    )


def _row_to_item(row: asyncpg.Record) -> DatasetSnapshotItemRecord:
    return DatasetSnapshotItemRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        snapshot_id=row["snapshot_id"],
        test_case_version_id=row["test_case_version_id"],
        sequence_index=row["sequence_index"],
        created_at=row["created_at"],
    )


class PostgresDatasetSnapshotRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_draft(
        self, *, tenant_id: UUID, dataset_id: UUID, created_by: UUID
    ) -> DatasetSnapshotRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                INSERT INTO dataset_snapshots (tenant_id, dataset_id, created_by)
                VALUES ($1, $2, $3)
                RETURNING {_SNAPSHOT_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                dataset_id,
                created_by,
            )
        assert row is not None
        return _row_to_snapshot(row)

    async def get_snapshot(
        self, *, tenant_id: UUID, snapshot_id: UUID
    ) -> DatasetSnapshotRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                SELECT {_SNAPSHOT_COLUMNS} FROM dataset_snapshots
                WHERE id = $1 AND tenant_id = $2
                """,  # noqa: S608
                snapshot_id,
                tenant_id,
            )
        return _row_to_snapshot(row) if row is not None else None

    async def add_item(
        self,
        *,
        tenant_id: UUID,
        snapshot_id: UUID,
        test_case_version_id: UUID,
        sequence_index: int,
    ) -> DatasetSnapshotItemRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            try:
                row = await connection.fetchrow(
                    f"""
                    INSERT INTO dataset_snapshot_items
                        (tenant_id, snapshot_id, test_case_version_id, sequence_index)
                    VALUES ($1, $2, $3, $4)
                    RETURNING {_ITEM_COLUMNS}
                    """,  # noqa: S608
                    tenant_id,
                    snapshot_id,
                    test_case_version_id,
                    sequence_index,
                )
            except asyncpg.exceptions.RaiseError as exc:
                raise SnapshotNotDraftError(str(exc)) from exc
        assert row is not None
        return _row_to_item(row)

    async def list_items(
        self, *, tenant_id: UUID, snapshot_id: UUID
    ) -> tuple[DatasetSnapshotItemRecord, ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            rows = await connection.fetch(
                f"""
                SELECT {_ITEM_COLUMNS} FROM dataset_snapshot_items
                WHERE snapshot_id = $1 AND tenant_id = $2
                ORDER BY sequence_index
                """,  # noqa: S608
                snapshot_id,
                tenant_id,
            )
        return tuple(_row_to_item(row) for row in rows)

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
    ) -> DatasetSnapshotRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            try:
                row = await connection.fetchrow(
                    f"""
                    UPDATE dataset_snapshots
                    SET status = 'finalized', content_hash = $3, hash_algorithm = $4,
                        canonicalization_version = $5, item_count = $6,
                        finalized_by = $7, finalized_at = now()
                    WHERE id = $1 AND tenant_id = $2
                    RETURNING {_SNAPSHOT_COLUMNS}
                    """,  # noqa: S608
                    snapshot_id,
                    tenant_id,
                    content_hash,
                    hash_algorithm,
                    canonicalization_version,
                    item_count,
                    finalized_by,
                )
            except asyncpg.exceptions.RaiseError as exc:
                raise SnapshotNotDraftError(str(exc)) from exc
        assert row is not None
        return _row_to_snapshot(row)
