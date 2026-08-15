"""Shared asyncpg connection pool for authenticated runtime queries.

Separate from ``PostgresConnectivityCheck``, which opens and closes an
ephemeral connection per readiness probe. Identity and tenancy
repositories reuse one pool created at application startup and closed
at shutdown.
"""

from __future__ import annotations

import asyncpg


async def create_pool(dsn: str, *, min_size: int = 1, max_size: int = 10) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn=dsn, min_size=min_size, max_size=max_size)
