"""PostgreSQL-backed run repository.

Run creation and finalization are both idempotent — see
``evalforge_api.adapters.idempotency_sql.with_idempotency`` for the
shared race-safe mechanism every write in this module builds on.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg

from evalforge_api.adapters.idempotency_sql import with_idempotency
from evalforge_api.adapters.rls_session import set_tenant_session
from evalforge_api.domain.ingestion_enums import RunStatus
from evalforge_api.ports.runs import RunRecord, RunToolVersionRecord

_RUN_COLUMNS = (
    "id, tenant_id, workspace_id, evaluation_target_id, model_version_id, prompt_version_id, "
    "retrieval_config_version_id, workflow_version_id, pricing_version_id, status, source, "
    "correlation_id, started_at, ended_at, metadata, schema_version, created_by, created_at, "
    "finalized_at"
)
_TOOL_VERSION_COLUMNS = "id, tenant_id, run_id, tool_definition_version_id, created_at"

_CREATE_RUN_OPERATION = "create_run"
_FINALIZE_RUN_OPERATION = "finalize_run"


class RunNotActiveError(Exception):
    """Raised when the ``forbid_terminal_run_mutation`` trigger rejects
    an update because the run already reached a terminal status."""


class RunNotFoundError(Exception):
    pass


def _row_to_run(row: asyncpg.Record) -> RunRecord:
    return RunRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        workspace_id=row["workspace_id"],
        evaluation_target_id=row["evaluation_target_id"],
        model_version_id=row["model_version_id"],
        prompt_version_id=row["prompt_version_id"],
        retrieval_config_version_id=row["retrieval_config_version_id"],
        workflow_version_id=row["workflow_version_id"],
        pricing_version_id=row["pricing_version_id"],
        status=RunStatus(row["status"]),
        source=row["source"],
        correlation_id=row["correlation_id"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        metadata=json.loads(row["metadata"]),
        schema_version=row["schema_version"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        finalized_at=row["finalized_at"],
    )


def _row_to_tool_version(row: asyncpg.Record) -> RunToolVersionRecord:
    return RunToolVersionRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        run_id=row["run_id"],
        tool_definition_version_id=row["tool_definition_version_id"],
        created_at=row["created_at"],
    )


class PostgresRunRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _fetch_run(
        self, connection: asyncpg.Connection, *, tenant_id: UUID, run_id: UUID
    ) -> RunRecord | None:
        row = await connection.fetchrow(
            f"SELECT {_RUN_COLUMNS} FROM runs WHERE id = $1 AND tenant_id = $2",  # noqa: S608
            run_id,
            tenant_id,
        )
        return _row_to_run(row) if row is not None else None

    async def create_run(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        evaluation_target_id: UUID | None,
        model_version_id: UUID | None,
        prompt_version_id: UUID | None,
        retrieval_config_version_id: UUID | None,
        workflow_version_id: UUID | None,
        pricing_version_id: UUID | None,
        source: str,
        correlation_id: str | None,
        started_at: datetime,
        metadata: dict[str, Any],
        schema_version: str,
        created_by: UUID,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[RunRecord, bool]:
        async def _set_session(connection: asyncpg.Connection) -> None:
            await set_tenant_session(connection, tenant_id=tenant_id)

        async def _fetch(connection: asyncpg.Connection, run_id: UUID) -> RunRecord | None:
            return await self._fetch_run(connection, tenant_id=tenant_id, run_id=run_id)

        async def _insert(connection: asyncpg.Connection) -> RunRecord:
            row = await connection.fetchrow(
                f"""
                INSERT INTO runs (
                    tenant_id, workspace_id, evaluation_target_id, model_version_id,
                    prompt_version_id, retrieval_config_version_id, workflow_version_id,
                    pricing_version_id, source, correlation_id, started_at, metadata,
                    schema_version, created_by
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13, $14)
                RETURNING {_RUN_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                workspace_id,
                evaluation_target_id,
                model_version_id,
                prompt_version_id,
                retrieval_config_version_id,
                workflow_version_id,
                pricing_version_id,
                source,
                correlation_id,
                started_at,
                json.dumps(metadata),
                schema_version,
                created_by,
            )
            assert row is not None
            return _row_to_run(row)

        return await with_idempotency(
            self._pool,
            tenant_id=tenant_id,
            operation=_CREATE_RUN_OPERATION,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            resource_type="run",
            created_by=created_by,
            set_session=_set_session,
            fetch_by_id=_fetch,
            perform=_insert,
            resource_id_of=lambda run: run.id,
        )

    async def get_run(self, *, tenant_id: UUID, run_id: UUID) -> RunRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            return await self._fetch_run(connection, tenant_id=tenant_id, run_id=run_id)

    async def finalize_run(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        status: RunStatus,
        ended_at: datetime,
        metadata: dict[str, Any] | None,
        created_by: UUID,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[RunRecord, bool]:
        async def _set_session(connection: asyncpg.Connection) -> None:
            await set_tenant_session(connection, tenant_id=tenant_id)

        async def _fetch(connection: asyncpg.Connection, resource_id: UUID) -> RunRecord | None:
            return await self._fetch_run(connection, tenant_id=tenant_id, run_id=resource_id)

        async def _update(connection: asyncpg.Connection) -> RunRecord:
            try:
                row = await connection.fetchrow(
                    f"""
                    UPDATE runs
                    SET status = $3, ended_at = $4, finalized_at = now(),
                        metadata = COALESCE($5::jsonb, metadata)
                    WHERE id = $1 AND tenant_id = $2
                    RETURNING {_RUN_COLUMNS}
                    """,  # noqa: S608
                    run_id,
                    tenant_id,
                    status.value,
                    ended_at,
                    json.dumps(metadata) if metadata is not None else None,
                )
            except asyncpg.exceptions.RaiseError as exc:
                raise RunNotActiveError(str(exc)) from exc
            if row is None:
                raise RunNotFoundError(str(run_id))
            return _row_to_run(row)

        return await with_idempotency(
            self._pool,
            tenant_id=tenant_id,
            operation=_FINALIZE_RUN_OPERATION,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            resource_type="run",
            created_by=created_by,
            set_session=_set_session,
            fetch_by_id=_fetch,
            perform=_update,
            resource_id_of=lambda run: run.id,
        )

    async def add_tool_version(
        self, *, tenant_id: UUID, run_id: UUID, tool_definition_version_id: UUID
    ) -> RunToolVersionRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                INSERT INTO run_tool_versions (tenant_id, run_id, tool_definition_version_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (run_id, tool_definition_version_id)
                    DO UPDATE SET run_id = EXCLUDED.run_id
                RETURNING {_TOOL_VERSION_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                run_id,
                tool_definition_version_id,
            )
        assert row is not None
        return _row_to_tool_version(row)

    async def list_tool_versions(
        self, *, tenant_id: UUID, run_id: UUID
    ) -> tuple[RunToolVersionRecord, ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            rows = await connection.fetch(
                f"""
                SELECT {_TOOL_VERSION_COLUMNS} FROM run_tool_versions
                WHERE run_id = $1 AND tenant_id = $2
                """,  # noqa: S608
                run_id,
                tenant_id,
            )
        return tuple(_row_to_tool_version(row) for row in rows)
