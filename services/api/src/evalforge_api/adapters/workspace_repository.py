"""PostgreSQL-backed workspace and evaluation-target repositories."""

from __future__ import annotations

from uuid import UUID

import asyncpg

from evalforge_api.adapters.rls_session import set_tenant_session
from evalforge_api.domain.evaluation_enums import EvaluationTargetStatus, WorkspaceStatus
from evalforge_api.ports.workspaces import EvaluationTargetRecord, WorkspaceRecord

_WORKSPACE_COLUMNS = "id, tenant_id, slug, name, status, created_by, created_at"
_TARGET_COLUMNS = "id, tenant_id, workspace_id, name, target_type, status, created_by, created_at"


def _row_to_workspace(row: asyncpg.Record) -> WorkspaceRecord:
    return WorkspaceRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        slug=row["slug"],
        name=row["name"],
        status=WorkspaceStatus(row["status"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def _row_to_target(row: asyncpg.Record) -> EvaluationTargetRecord:
    return EvaluationTargetRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        workspace_id=row["workspace_id"],
        name=row["name"],
        target_type=row["target_type"],
        status=EvaluationTargetStatus(row["status"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


class PostgresWorkspaceRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(
        self, *, tenant_id: UUID, slug: str, name: str, created_by: UUID
    ) -> WorkspaceRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                INSERT INTO workspaces (tenant_id, slug, name, created_by)
                VALUES ($1, $2, $3, $4)
                RETURNING {_WORKSPACE_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                slug,
                name,
                created_by,
            )
        assert row is not None
        return _row_to_workspace(row)

    async def get_by_id(self, *, tenant_id: UUID, workspace_id: UUID) -> WorkspaceRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                SELECT {_WORKSPACE_COLUMNS} FROM workspaces
                WHERE id = $1 AND tenant_id = $2
                """,  # noqa: S608
                workspace_id,
                tenant_id,
            )
        return _row_to_workspace(row) if row is not None else None

    async def list_for_tenant(self, *, tenant_id: UUID) -> tuple[WorkspaceRecord, ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            rows = await connection.fetch(
                f"SELECT {_WORKSPACE_COLUMNS} FROM workspaces WHERE tenant_id = $1",  # noqa: S608
                tenant_id,
            )
        return tuple(_row_to_workspace(row) for row in rows)


class PostgresEvaluationTargetRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        name: str,
        target_type: str,
        created_by: UUID,
    ) -> EvaluationTargetRecord:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                INSERT INTO evaluation_targets
                    (tenant_id, workspace_id, name, target_type, created_by)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING {_TARGET_COLUMNS}
                """,  # noqa: S608
                tenant_id,
                workspace_id,
                name,
                target_type,
                created_by,
            )
        assert row is not None
        return _row_to_target(row)

    async def get_by_id(self, *, tenant_id: UUID, target_id: UUID) -> EvaluationTargetRecord | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            row = await connection.fetchrow(
                f"""
                SELECT {_TARGET_COLUMNS} FROM evaluation_targets
                WHERE id = $1 AND tenant_id = $2
                """,  # noqa: S608
                target_id,
                tenant_id,
            )
        return _row_to_target(row) if row is not None else None

    async def list_for_workspace(
        self, *, tenant_id: UUID, workspace_id: UUID
    ) -> tuple[EvaluationTargetRecord, ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            rows = await connection.fetch(
                f"""
                SELECT {_TARGET_COLUMNS} FROM evaluation_targets
                WHERE workspace_id = $1 AND tenant_id = $2
                """,  # noqa: S608
                workspace_id,
                tenant_id,
            )
        return tuple(_row_to_target(row) for row in rows)
