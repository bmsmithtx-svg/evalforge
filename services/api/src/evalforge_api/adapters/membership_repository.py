"""PostgreSQL-backed tenant-membership repository.

``tenant_memberships`` carries row-level security policies (see the
identity-and-tenancy migration) that only admit rows matching the
current transaction's ``app.current_user_id`` or ``app.current_tenant_id``
session settings. Every query here sets those settings, inside the same
transaction as the query, from server-verified identity — never from a
client-supplied value — so a missing or buggy ``WHERE`` clause in this
file, or in code added later, still cannot return another tenant's rows.
Settings are transaction-local (``set_config(..., true)``) so they never
leak to a connection reused by a later, unrelated request.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

from evalforge_api.domain.enums import MembershipStatus, TenantRole
from evalforge_api.ports.identity import MembershipRecord

_SELECT_COLUMNS = "id, user_id, tenant_id, role, status, created_at"


def _row_to_membership(row: asyncpg.Record) -> MembershipRecord:
    return MembershipRecord(
        id=row["id"],
        user_id=row["user_id"],
        tenant_id=row["tenant_id"],
        role=TenantRole(row["role"]),
        status=MembershipStatus(row["status"]),
        created_at=row["created_at"],
    )


class PostgresMembershipRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, *, user_id: UUID, tenant_id: UUID, role: TenantRole) -> MembershipRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await connection.execute(
                "SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_id)
            )
            await connection.execute(
                "SELECT set_config('app.current_user_id', $1, true)", str(user_id)
            )
            # _SELECT_COLUMNS is a fixed module constant, not request
            # input; every real value below is bound as a query parameter.
            row = await connection.fetchrow(
                f"""
                INSERT INTO tenant_memberships (user_id, tenant_id, role)
                VALUES ($1, $2, $3)
                RETURNING {_SELECT_COLUMNS}
                """,  # noqa: S608
                user_id,
                tenant_id,
                role.value,
            )
        assert row is not None
        return _row_to_membership(row)

    async def get_membership(self, *, user_id: UUID, tenant_id: UUID) -> MembershipRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await connection.execute(
                "SELECT set_config('app.current_user_id', $1, true)", str(user_id)
            )
            row = await connection.fetchrow(
                f"""
                SELECT {_SELECT_COLUMNS} FROM tenant_memberships
                WHERE user_id = $1 AND tenant_id = $2
                """,  # noqa: S608
                user_id,
                tenant_id,
            )
        return _row_to_membership(row) if row is not None else None

    async def list_for_user(self, user_id: UUID) -> tuple[MembershipRecord, ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await connection.execute(
                "SELECT set_config('app.current_user_id', $1, true)", str(user_id)
            )
            rows = await connection.fetch(
                f"SELECT {_SELECT_COLUMNS} FROM tenant_memberships WHERE user_id = $1",  # noqa: S608
                user_id,
            )
        return tuple(_row_to_membership(row) for row in rows)

    async def list_for_tenant(
        self, *, tenant_id: UUID, requesting_user_id: UUID
    ) -> tuple[MembershipRecord, ...]:
        """List every member of ``tenant_id``.

        Callers must independently verify ``requesting_user_id`` holds
        an authorized role in ``tenant_id`` before calling this — the
        RLS session settings here are defense-in-depth, not the
        authorization decision itself.
        """
        async with self._pool.acquire() as connection, connection.transaction():
            await connection.execute(
                "SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_id)
            )
            await connection.execute(
                "SELECT set_config('app.current_user_id', $1, true)", str(requesting_user_id)
            )
            rows = await connection.fetch(
                f"SELECT {_SELECT_COLUMNS} FROM tenant_memberships WHERE tenant_id = $1",  # noqa: S608
                tenant_id,
            )
        return tuple(_row_to_membership(row) for row in rows)
