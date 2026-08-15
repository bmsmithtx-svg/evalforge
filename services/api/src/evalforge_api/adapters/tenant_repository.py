"""PostgreSQL-backed tenant repository.

Tenants are not owned by another tenant, so no row-level security
policy applies here; the table itself defines the isolation boundary
that other tenant-owned tables reference.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

from evalforge_api.domain.enums import TenantStatus
from evalforge_api.ports.identity import TenantRecord

_SELECT_COLUMNS = "id, slug, name, status, created_at"


class PostgresTenantRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_id(self, tenant_id: UUID) -> TenantRecord | None:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                f"SELECT {_SELECT_COLUMNS} FROM tenants WHERE id = $1",  # noqa: S608
                tenant_id,
            )
        if row is None:
            return None
        return TenantRecord(
            id=row["id"],
            slug=row["slug"],
            name=row["name"],
            status=TenantStatus(row["status"]),
            created_at=row["created_at"],
        )
