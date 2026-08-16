"""PostgreSQL-backed trace repository.

Trace creation and finalization are both idempotent — see
``evalforge_api.adapters.idempotency_sql.with_idempotency``.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg

from evalforge_api.adapters.idempotency_sql import with_idempotency
from evalforge_api.adapters.rls_session import set_tenant_session
from evalforge_api.domain.ingestion_enums import TraceStatus
from evalforge_api.ports.traces import TraceRecord

_TRACE_COLUMNS = (
    "id, tenant_id, workspace_id, run_id, status, source, provider_trace_id, correlation_id, "
    "started_at, ended_at, metadata, schema_version, created_by, created_at, finalized_at"
)

_CREATE_TRACE_OPERATION = "create_trace"
_FINALIZE_TRACE_OPERATION = "finalize_trace"


class TraceNotActiveError(Exception):
    """Raised when the ``forbid_finalized_trace_mutation`` trigger
    rejects an update because the trace is already finalized."""


class TraceNotFoundError(Exception):
    pass


def _row_to_trace(row: asyncpg.Record) -> TraceRecord:
    return TraceRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        workspace_id=row["workspace_id"],
        run_id=row["run_id"],
        status=TraceStatus(row["status"]),
        source=row["source"],
        provider_trace_id=row["provider_trace_id"],
        correlation_id=row["correlation_id"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        metadata=json.loads(row["metadata"]),
        schema_version=row["schema_version"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        finalized_at=row["finalized_at"],
    )


class PostgresTraceRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _fetch_trace(
        self, connection: asyncpg.Connection, *, tenant_id: UUID, trace_id: UUID
    ) -> TraceRecord | None:
        row = await connection.fetchrow(
            f"SELECT {_TRACE_COLUMNS} FROM traces WHERE id = $1 AND tenant_id = $2",  # noqa: S608
            trace_id,
            tenant_id,
        )
        return _row_to_trace(row) if row is not None else None

    async def create_trace(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        run_id: UUID,
        source: str,
        provider_trace_id: str | None,
        correlation_id: str | None,
        metadata: dict[str, Any],
        schema_version: str,
        created_by: UUID,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[TraceRecord, bool]:
        async def _set_session(connection: asyncpg.Connection) -> None:
            await set_tenant_session(connection, tenant_id=tenant_id)

        async def _fetch(connection: asyncpg.Connection, trace_id: UUID) -> TraceRecord | None:
            return await self._fetch_trace(connection, tenant_id=tenant_id, trace_id=trace_id)

        async def _insert(connection: asyncpg.Connection) -> TraceRecord:
            row = await connection.fetchrow(
                f"""
                INSERT INTO traces (
                    tenant_id, workspace_id, run_id, source, provider_trace_id,
                    correlation_id, metadata, schema_version, created_by
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)
                RETURNING {_TRACE_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                workspace_id,
                run_id,
                source,
                provider_trace_id,
                correlation_id,
                json.dumps(metadata),
                schema_version,
                created_by,
            )
            assert row is not None
            return _row_to_trace(row)

        return await with_idempotency(
            self._pool,
            tenant_id=tenant_id,
            operation=_CREATE_TRACE_OPERATION,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            resource_type="trace",
            created_by=created_by,
            set_session=_set_session,
            fetch_by_id=_fetch,
            perform=_insert,
            resource_id_of=lambda trace: trace.id,
        )

    async def get_trace(self, *, tenant_id: UUID, trace_id: UUID) -> TraceRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            return await self._fetch_trace(connection, tenant_id=tenant_id, trace_id=trace_id)

    async def finalize_trace(
        self,
        *,
        tenant_id: UUID,
        trace_id: UUID,
        started_at: datetime | None,
        ended_at: datetime | None,
        created_by: UUID,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[TraceRecord, bool]:
        async def _set_session(connection: asyncpg.Connection) -> None:
            await set_tenant_session(connection, tenant_id=tenant_id)

        async def _fetch(connection: asyncpg.Connection, resource_id: UUID) -> TraceRecord | None:
            return await self._fetch_trace(connection, tenant_id=tenant_id, trace_id=resource_id)

        async def _update(connection: asyncpg.Connection) -> TraceRecord:
            try:
                row = await connection.fetchrow(
                    f"""
                    UPDATE traces
                    SET status = 'finalized', finalized_at = now(),
                        started_at = COALESCE($3, started_at), ended_at = COALESCE($4, ended_at)
                    WHERE id = $1 AND tenant_id = $2
                    RETURNING {_TRACE_COLUMNS}
                    """,  # noqa: S608
                    trace_id,
                    tenant_id,
                    started_at,
                    ended_at,
                )
            except asyncpg.exceptions.RaiseError as exc:
                raise TraceNotActiveError(str(exc)) from exc
            if row is None:
                raise TraceNotFoundError(str(trace_id))
            return _row_to_trace(row)

        return await with_idempotency(
            self._pool,
            tenant_id=tenant_id,
            operation=_FINALIZE_TRACE_OPERATION,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            resource_type="trace",
            created_by=created_by,
            set_session=_set_session,
            fetch_by_id=_fetch,
            perform=_update,
            resource_id_of=lambda trace: trace.id,
        )
