"""Shared helper to populate the PostgreSQL row-level-security session
setting every evaluation-domain repository depends on.

Every repository under this package sets ``app.current_tenant_id``
inside the same transaction as the query it protects, from a
server-verified ``tenant_id`` — never from client-supplied input —
exactly as ``evalforge_api.adapters.membership_repository`` does for
the identity tables.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def set_tenant_session(connection: asyncpg.Connection, *, tenant_id: UUID) -> None:
    await connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_id))
