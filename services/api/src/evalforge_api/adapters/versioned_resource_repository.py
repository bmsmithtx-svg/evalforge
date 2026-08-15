"""PostgreSQL-backed versioned-resource repository.

``content`` is stored as JSONB. asyncpg has no built-in JSON codec
registered on the shared pool, so this adapter encodes to text on the
way in (cast with ``::jsonb``) and decodes on the way out — the only
place in the evaluation domain that touches JSON serialization
directly; hashing always operates on the domain-canonicalized bytes
computed before this adapter is called, never on this codec's output.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import asyncpg

from evalforge_api.adapters.rls_session import set_tenant_session
from evalforge_api.domain.evaluation_enums import (
    ResourceKind,
    RetentionClass,
    VersionedResourceStatus,
)
from evalforge_api.ports.versioned_resources import (
    VersionedResourceRecord,
    VersionedResourceVersionRecord,
)

_RESOURCE_COLUMNS = "id, tenant_id, workspace_id, kind, name, status, created_by, created_at"
_VERSION_COLUMNS = (
    "id, tenant_id, resource_id, version_number, content, content_hash, hash_algorithm, "
    "canonicalization_version, derived_from_version_id, retention_class, retain_until, "
    "archived_at, created_by, created_at"
)


def _row_to_resource(row: asyncpg.Record) -> VersionedResourceRecord:
    return VersionedResourceRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        workspace_id=row["workspace_id"],
        kind=ResourceKind(row["kind"]),
        name=row["name"],
        status=VersionedResourceStatus(row["status"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def _row_to_version(row: asyncpg.Record) -> VersionedResourceVersionRecord:
    return VersionedResourceVersionRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        resource_id=row["resource_id"],
        version_number=row["version_number"],
        content=json.loads(row["content"]),
        content_hash=row["content_hash"],
        hash_algorithm=row["hash_algorithm"],
        canonicalization_version=row["canonicalization_version"],
        derived_from_version_id=row["derived_from_version_id"],
        retention_class=RetentionClass(row["retention_class"]),
        retain_until=row["retain_until"],
        archived_at=row["archived_at"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


class PostgresVersionedResourceRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_resource(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        kind: ResourceKind,
        name: str,
        created_by: UUID,
    ) -> VersionedResourceRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                INSERT INTO versioned_resources (tenant_id, workspace_id, kind, name, created_by)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING {_RESOURCE_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                workspace_id,
                kind.value,
                name,
                created_by,
            )
        assert row is not None
        return _row_to_resource(row)

    async def get_resource(
        self, *, tenant_id: UUID, resource_id: UUID
    ) -> VersionedResourceRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                SELECT {_RESOURCE_COLUMNS} FROM versioned_resources
                WHERE id = $1 AND tenant_id = $2
                """,  # noqa: S608
                resource_id,
                tenant_id,
            )
        return _row_to_resource(row) if row is not None else None

    async def create_version(
        self,
        *,
        tenant_id: UUID,
        resource_id: UUID,
        version_number: int,
        content: dict[str, Any],
        content_hash: str,
        hash_algorithm: str,
        canonicalization_version: str,
        derived_from_version_id: UUID | None,
        created_by: UUID,
    ) -> VersionedResourceVersionRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                INSERT INTO versioned_resource_versions (
                    tenant_id, resource_id, version_number, content, content_hash,
                    hash_algorithm, canonicalization_version, derived_from_version_id, created_by
                )
                VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9)
                RETURNING {_VERSION_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                resource_id,
                version_number,
                json.dumps(content),
                content_hash,
                hash_algorithm,
                canonicalization_version,
                derived_from_version_id,
                created_by,
            )
        assert row is not None
        return _row_to_version(row)

    async def get_version(
        self, *, tenant_id: UUID, version_id: UUID
    ) -> VersionedResourceVersionRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                SELECT {_VERSION_COLUMNS} FROM versioned_resource_versions
                WHERE id = $1 AND tenant_id = $2
                """,  # noqa: S608
                version_id,
                tenant_id,
            )
        return _row_to_version(row) if row is not None else None

    async def list_versions(
        self, *, tenant_id: UUID, resource_id: UUID
    ) -> tuple[VersionedResourceVersionRecord, ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            rows = await connection.fetch(
                f"""
                SELECT {_VERSION_COLUMNS} FROM versioned_resource_versions
                WHERE resource_id = $1 AND tenant_id = $2
                ORDER BY version_number
                """,  # noqa: S608
                resource_id,
                tenant_id,
            )
        return tuple(_row_to_version(row) for row in rows)
