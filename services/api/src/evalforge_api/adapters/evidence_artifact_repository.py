"""PostgreSQL-backed run/trace evidence-artifact linkage repository.

Attaches an existing Milestone 4 artifact version (created through
``evalforge_api.application.artifact_service``) to a run or trace as
supporting evidence. This repository never touches artifact bytes or
metadata itself — only the join row.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

from evalforge_api.adapters.idempotency_sql import with_idempotency
from evalforge_api.adapters.rls_session import set_tenant_session
from evalforge_api.ports.evidence_artifacts import EvidenceArtifactRecord

_COLUMNS = "id, tenant_id, run_id, trace_id, artifact_version_id, role, created_at"

_ATTACH_EVIDENCE_OPERATION = "attach_evidence_artifact"


def _row_to_record(row: asyncpg.Record) -> EvidenceArtifactRecord:
    return EvidenceArtifactRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        run_id=row["run_id"],
        trace_id=row["trace_id"],
        artifact_version_id=row["artifact_version_id"],
        role=row["role"],
        created_at=row["created_at"],
    )


class PostgresEvidenceArtifactRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def attach(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID | None,
        trace_id: UUID | None,
        artifact_version_id: UUID,
        role: str,
        created_by: UUID,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[EvidenceArtifactRecord, bool]:
        async def _set_session(connection: asyncpg.Connection) -> None:
            await set_tenant_session(connection, tenant_id=tenant_id)

        async def _fetch(
            connection: asyncpg.Connection, resource_id: UUID
        ) -> EvidenceArtifactRecord | None:
            row = await connection.fetchrow(
                f"SELECT {_COLUMNS} FROM run_evidence_artifacts "  # noqa: S608
                "WHERE id = $1 AND tenant_id = $2",
                resource_id,
                tenant_id,
            )
            return _row_to_record(row) if row is not None else None

        async def _insert(connection: asyncpg.Connection) -> EvidenceArtifactRecord:
            row = await connection.fetchrow(
                f"""
                INSERT INTO run_evidence_artifacts
                    (tenant_id, run_id, trace_id, artifact_version_id, role, created_by)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING {_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                run_id,
                trace_id,
                artifact_version_id,
                role,
                created_by,
            )
            assert row is not None
            return _row_to_record(row)

        return await with_idempotency(
            self._pool,
            tenant_id=tenant_id,
            operation=_ATTACH_EVIDENCE_OPERATION,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            resource_type="run_evidence_artifact",
            created_by=created_by,
            set_session=_set_session,
            fetch_by_id=_fetch,
            perform=_insert,
            resource_id_of=lambda record: record.id,
        )

    async def list_for_run(
        self, *, tenant_id: UUID, run_id: UUID
    ) -> tuple[EvidenceArtifactRecord, ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            rows = await connection.fetch(
                f"SELECT {_COLUMNS} FROM run_evidence_artifacts "  # noqa: S608
                "WHERE run_id = $1 AND tenant_id = $2",
                run_id,
                tenant_id,
            )
        return tuple(_row_to_record(row) for row in rows)

    async def list_for_trace(
        self, *, tenant_id: UUID, trace_id: UUID
    ) -> tuple[EvidenceArtifactRecord, ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            rows = await connection.fetch(
                f"SELECT {_COLUMNS} FROM run_evidence_artifacts "  # noqa: S608
                "WHERE trace_id = $1 AND tenant_id = $2",
                trace_id,
                tenant_id,
            )
        return tuple(_row_to_record(row) for row in rows)
