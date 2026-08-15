"""PostgreSQL-backed artifact metadata repository.

Object bytes live in ``evalforge_api.adapters.artifact_object_storage``;
this repository only persists metadata, hash, and lineage references.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

from evalforge_api.adapters.rls_session import set_tenant_session
from evalforge_api.domain.evaluation_enums import ArtifactStatus, RetentionClass
from evalforge_api.ports.artifacts import ArtifactRecord, ArtifactVersionRecord

_ARTIFACT_COLUMNS = (
    "id, tenant_id, workspace_id, media_type, purpose, status, created_by, created_at"
)
_VERSION_COLUMNS = (
    "id, tenant_id, artifact_id, version_number, content_hash, hash_algorithm, byte_size, "
    "content_type, storage_key, derived_from_artifact_version_id, retention_class, "
    "retain_until, archived_at, created_by, created_at"
)


def _row_to_artifact(row: asyncpg.Record) -> ArtifactRecord:
    return ArtifactRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        workspace_id=row["workspace_id"],
        media_type=row["media_type"],
        purpose=row["purpose"],
        status=ArtifactStatus(row["status"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def _row_to_version(row: asyncpg.Record) -> ArtifactVersionRecord:
    return ArtifactVersionRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        artifact_id=row["artifact_id"],
        version_number=row["version_number"],
        content_hash=row["content_hash"],
        hash_algorithm=row["hash_algorithm"],
        byte_size=row["byte_size"],
        content_type=row["content_type"],
        storage_key=row["storage_key"],
        derived_from_artifact_version_id=row["derived_from_artifact_version_id"],
        retention_class=RetentionClass(row["retention_class"]),
        retain_until=row["retain_until"],
        archived_at=row["archived_at"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


class PostgresArtifactRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_artifact(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID | None,
        media_type: str,
        purpose: str,
        created_by: UUID,
    ) -> ArtifactRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                INSERT INTO artifacts (tenant_id, workspace_id, media_type, purpose, created_by)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING {_ARTIFACT_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                workspace_id,
                media_type,
                purpose,
                created_by,
            )
        assert row is not None
        return _row_to_artifact(row)

    async def get_artifact(self, *, tenant_id: UUID, artifact_id: UUID) -> ArtifactRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"SELECT {_ARTIFACT_COLUMNS} FROM artifacts WHERE id = $1 AND tenant_id = $2",  # noqa: S608
                artifact_id,
                tenant_id,
            )
        return _row_to_artifact(row) if row is not None else None

    async def create_artifact_version(
        self,
        *,
        tenant_id: UUID,
        artifact_id: UUID,
        version_number: int,
        content_hash: str,
        hash_algorithm: str,
        byte_size: int,
        content_type: str,
        storage_key: str,
        derived_from_artifact_version_id: UUID | None,
        created_by: UUID,
    ) -> ArtifactVersionRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                INSERT INTO artifact_versions (
                    tenant_id, artifact_id, version_number, content_hash, hash_algorithm,
                    byte_size, content_type, storage_key, derived_from_artifact_version_id,
                    created_by
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING {_VERSION_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                artifact_id,
                version_number,
                content_hash,
                hash_algorithm,
                byte_size,
                content_type,
                storage_key,
                derived_from_artifact_version_id,
                created_by,
            )
        assert row is not None
        return _row_to_version(row)

    async def get_artifact_version(
        self, *, tenant_id: UUID, version_id: UUID
    ) -> ArtifactVersionRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                SELECT {_VERSION_COLUMNS} FROM artifact_versions
                WHERE id = $1 AND tenant_id = $2
                """,  # noqa: S608
                version_id,
                tenant_id,
            )
        return _row_to_version(row) if row is not None else None

    async def list_artifact_versions(
        self, *, tenant_id: UUID, artifact_id: UUID
    ) -> tuple[ArtifactVersionRecord, ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            rows = await connection.fetch(
                f"""
                SELECT {_VERSION_COLUMNS} FROM artifact_versions
                WHERE artifact_id = $1 AND tenant_id = $2
                ORDER BY version_number
                """,  # noqa: S608
                artifact_id,
                tenant_id,
            )
        return tuple(_row_to_version(row) for row in rows)
