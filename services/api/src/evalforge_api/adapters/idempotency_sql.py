"""Shared transactional idempotency helper for ingestion writes.

Every ingestion repository (runs, traces, spans, evidence artifacts)
follows the same pattern: insert or update the resource and record its
idempotency key in one transaction, so a lost race on the idempotency
table's unique constraint rolls back the resource write too — no
orphaned duplicate evidence can ever become visible. On that race, the
caller re-reads the winning record in a fresh transaction and returns
the existing resource instead of repeating the write. See
docs/THREAT_MODEL.md ("Replay attacks") and the Milestone 5 completion
report for the full semantics.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

import asyncpg

from evalforge_api.domain.ingestion import IdempotencyConflictError


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    resource_id: UUID
    request_fingerprint: str


async def find_idempotency_record(
    connection: asyncpg.Connection, *, tenant_id: UUID, operation: str, idempotency_key: str
) -> IdempotencyRecord | None:
    row = await connection.fetchrow(
        """
        SELECT resource_id, request_fingerprint FROM idempotency_records
        WHERE tenant_id = $1 AND operation = $2 AND idempotency_key = $3
        """,
        tenant_id,
        operation,
        idempotency_key,
    )
    if row is None:
        return None
    return IdempotencyRecord(
        resource_id=row["resource_id"], request_fingerprint=row["request_fingerprint"]
    )


async def record_idempotency_key(
    connection: asyncpg.Connection,
    *,
    tenant_id: UUID,
    operation: str,
    idempotency_key: str,
    request_fingerprint: str,
    resource_type: str,
    resource_id: UUID,
    created_by: UUID,
) -> None:
    """Raises ``asyncpg.exceptions.UniqueViolationError`` when another
    concurrent request already recorded this key first."""
    await connection.execute(
        """
        INSERT INTO idempotency_records
            (tenant_id, operation, idempotency_key, request_fingerprint,
             resource_type, resource_id, created_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        tenant_id,
        operation,
        idempotency_key,
        request_fingerprint,
        resource_type,
        resource_id,
        created_by,
    )


async def with_idempotency[T](
    pool: asyncpg.Pool,
    *,
    tenant_id: UUID,
    operation: str,
    idempotency_key: str,
    request_fingerprint: str,
    resource_type: str,
    created_by: UUID,
    set_session: Callable[[asyncpg.Connection], Awaitable[None]],
    fetch_by_id: Callable[[asyncpg.Connection, UUID], Awaitable[T | None]],
    perform: Callable[[asyncpg.Connection], Awaitable[T]],
    resource_id_of: Callable[[T], UUID],
) -> tuple[T, bool]:
    """Run ``perform`` (an INSERT or an UPDATE) exactly once per
    ``(tenant_id, operation, idempotency_key)``, replaying the prior
    result on a retried request instead of repeating the write.
    Returns ``(result, created)`` where ``created`` is ``False`` when
    an existing result was replayed.
    """

    async def _replay(connection: asyncpg.Connection) -> tuple[T, bool] | None:
        existing = await find_idempotency_record(
            connection, tenant_id=tenant_id, operation=operation, idempotency_key=idempotency_key
        )
        if existing is None:
            return None
        if existing.request_fingerprint != request_fingerprint:
            raise IdempotencyConflictError(idempotency_key)
        resource = await fetch_by_id(connection, existing.resource_id)
        assert resource is not None  # guaranteed by the FK the resource_id column carries
        return resource, False

    try:
        async with pool.acquire() as connection, connection.transaction():
            await set_session(connection)
            replayed = await _replay(connection)
            if replayed is not None:
                return replayed
            result = await perform(connection)
            await record_idempotency_key(
                connection,
                tenant_id=tenant_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                resource_type=resource_type,
                resource_id=resource_id_of(result),
                created_by=created_by,
            )
            return result, True
    except asyncpg.exceptions.UniqueViolationError:
        pass  # lost the race on the idempotency key; re-read the winner below

    async with pool.acquire() as connection, connection.transaction():
        await set_session(connection)
        replayed = await _replay(connection)
        assert replayed is not None
        return replayed
