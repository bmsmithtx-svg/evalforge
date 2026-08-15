"""PostgreSQL connectivity adapter."""

from __future__ import annotations

import asyncpg
import structlog

from evalforge_api.ports.connectivity import ConnectivityResult

logger = structlog.get_logger(__name__)


class PostgresConnectivityCheck:
    def __init__(self, dsn: str, *, timeout_seconds: float) -> None:
        self._dsn = dsn
        self._timeout_seconds = timeout_seconds

    async def check(self) -> ConnectivityResult:
        try:
            connection = await asyncpg.connect(dsn=self._dsn, timeout=self._timeout_seconds)
        except (OSError, asyncpg.PostgresError) as exc:
            logger.warning("postgres_connectivity_check_failed", error=type(exc).__name__)
            return ConnectivityResult(name="postgres", ok=False, detail=type(exc).__name__)

        try:
            await connection.fetchval("SELECT 1")
        except asyncpg.PostgresError as exc:
            logger.warning("postgres_connectivity_query_failed", error=type(exc).__name__)
            return ConnectivityResult(name="postgres", ok=False, detail=type(exc).__name__)
        finally:
            await connection.close()

        return ConnectivityResult(name="postgres", ok=True)
