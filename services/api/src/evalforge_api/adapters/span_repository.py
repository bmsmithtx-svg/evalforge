"""PostgreSQL-backed span repository.

A span batch is ingested as one idempotent unit: every span in the
request is inserted inside a single transaction, and a repeated
request with the same idempotency key replays exactly the spans that
batch created (identified by ``batch_id``) rather than re-inserting
them. Parent references are resolved by the caller-assigned
``provider_span_id`` — either earlier in the same batch or already
persisted in the same trace from a prior batch; anything else is
rejected rather than guessed at (docs/THREAT_MODEL.md, "Trace and
artifact poisoning").
"""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import UUID, uuid4

import asyncpg

from evalforge_api.adapters.idempotency_sql import with_idempotency
from evalforge_api.adapters.rls_session import set_tenant_session
from evalforge_api.domain.ingestion import SpanParentNotFoundError
from evalforge_api.domain.ingestion_enums import SpanKind, SpanStatus
from evalforge_api.ports.traces import SpanInput, SpanRecord

_SPAN_COLUMNS = (
    "id, tenant_id, trace_id, batch_id, parent_span_id, provider_span_id, name, span_kind, "
    "status, error_message, started_at, ended_at, model_version_id, retrieval_config_version_id, "
    "tool_definition_version_id, workflow_version_id, attributes, input_artifact_version_id, "
    "output_artifact_version_id, token_count_input, token_count_output, cost_amount, "
    "cost_currency, created_by, created_at"
)

_INGEST_SPANS_OPERATION = "ingest_spans"


class SpanInsertRejectedError(Exception):
    """Raised when the ``validate_span_insert`` trigger rejects a span:
    the trace is no longer ingesting, or the parent-span relationship
    is structurally invalid (cross-trace or self-parent)."""


def _row_to_span(row: asyncpg.Record) -> SpanRecord:
    return SpanRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        trace_id=row["trace_id"],
        batch_id=row["batch_id"],
        parent_span_id=row["parent_span_id"],
        provider_span_id=row["provider_span_id"],
        name=row["name"],
        span_kind=SpanKind(row["span_kind"]),
        status=SpanStatus(row["status"]),
        error_message=row["error_message"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        model_version_id=row["model_version_id"],
        retrieval_config_version_id=row["retrieval_config_version_id"],
        tool_definition_version_id=row["tool_definition_version_id"],
        workflow_version_id=row["workflow_version_id"],
        attributes=json.loads(row["attributes"]),
        input_artifact_version_id=row["input_artifact_version_id"],
        output_artifact_version_id=row["output_artifact_version_id"],
        token_count_input=row["token_count_input"],
        token_count_output=row["token_count_output"],
        cost_amount=Decimal(row["cost_amount"]) if row["cost_amount"] is not None else None,
        cost_currency=row["cost_currency"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


class PostgresSpanRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _resolve_parent_id(
        self,
        connection: asyncpg.Connection,
        *,
        tenant_id: UUID,
        trace_id: UUID,
        provider_parent_span_id: str,
        ids_seen_in_batch: dict[str, UUID],
    ) -> UUID:
        if provider_parent_span_id in ids_seen_in_batch:
            return ids_seen_in_batch[provider_parent_span_id]
        row = await connection.fetchrow(
            "SELECT id FROM spans WHERE trace_id = $1 AND tenant_id = $2 AND provider_span_id = $3",
            trace_id,
            tenant_id,
            provider_parent_span_id,
        )
        if row is None:
            raise SpanParentNotFoundError(provider_parent_span_id)
        parent_id: UUID = row["id"]
        return parent_id

    async def ingest_batch(
        self,
        *,
        tenant_id: UUID,
        trace_id: UUID,
        spans: tuple[SpanInput, ...],
        created_by: UUID,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[tuple[SpanRecord, ...], bool]:
        batch_id = uuid4()

        async def _set_session(connection: asyncpg.Connection) -> None:
            await set_tenant_session(connection, tenant_id=tenant_id)

        async def _fetch(
            connection: asyncpg.Connection, resource_id: UUID
        ) -> tuple[SpanRecord, ...] | None:
            rows = await connection.fetch(
                f"SELECT {_SPAN_COLUMNS} FROM spans "  # noqa: S608
                "WHERE batch_id = $1 AND tenant_id = $2 ORDER BY created_at",
                resource_id,
                tenant_id,
            )
            if not rows:
                return None
            return tuple(_row_to_span(row) for row in rows)

        async def _insert(connection: asyncpg.Connection) -> tuple[SpanRecord, ...]:
            ids_seen_in_batch: dict[str, UUID] = {}
            inserted: list[SpanRecord] = []
            for span_input in spans:
                parent_id: UUID | None = None
                if span_input.provider_parent_span_id is not None:
                    parent_id = await self._resolve_parent_id(
                        connection,
                        tenant_id=tenant_id,
                        trace_id=trace_id,
                        provider_parent_span_id=span_input.provider_parent_span_id,
                        ids_seen_in_batch=ids_seen_in_batch,
                    )
                try:
                    row = await connection.fetchrow(
                        f"""
                        INSERT INTO spans (
                            tenant_id, trace_id, batch_id, parent_span_id, provider_span_id, name,
                            span_kind, status, error_message, started_at, ended_at,
                            model_version_id, retrieval_config_version_id,
                            tool_definition_version_id, workflow_version_id, attributes,
                            input_artifact_version_id, output_artifact_version_id,
                            token_count_input, token_count_output, cost_amount, cost_currency,
                            created_by
                        )
                        VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                            $16::jsonb, $17, $18, $19, $20, $21, $22, $23
                        )
                        RETURNING {_SPAN_COLUMNS}
                        """,  # noqa: S608
                        tenant_id,
                        trace_id,
                        batch_id,
                        parent_id,
                        span_input.provider_span_id,
                        span_input.name,
                        span_input.span_kind.value,
                        span_input.status.value,
                        span_input.error_message,
                        span_input.started_at,
                        span_input.ended_at,
                        span_input.model_version_id,
                        span_input.retrieval_config_version_id,
                        span_input.tool_definition_version_id,
                        span_input.workflow_version_id,
                        json.dumps(span_input.attributes),
                        span_input.input_artifact_version_id,
                        span_input.output_artifact_version_id,
                        span_input.token_count_input,
                        span_input.token_count_output,
                        span_input.cost_amount,
                        span_input.cost_currency,
                        created_by,
                    )
                except asyncpg.exceptions.RaiseError as exc:
                    raise SpanInsertRejectedError(str(exc)) from exc
                assert row is not None
                record = _row_to_span(row)
                inserted.append(record)
                if span_input.provider_span_id:
                    ids_seen_in_batch[span_input.provider_span_id] = record.id
            return tuple(inserted)

        return await with_idempotency(
            self._pool,
            tenant_id=tenant_id,
            operation=_INGEST_SPANS_OPERATION,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            resource_type="span_batch",
            created_by=created_by,
            set_session=_set_session,
            fetch_by_id=_fetch,
            perform=_insert,
            resource_id_of=lambda _records: batch_id,
        )

    async def list_for_trace(self, *, tenant_id: UUID, trace_id: UUID) -> tuple[SpanRecord, ...]:
        async with self._pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=tenant_id)
            rows = await connection.fetch(
                f"SELECT {_SPAN_COLUMNS} FROM spans "  # noqa: S608
                "WHERE trace_id = $1 AND tenant_id = $2 ORDER BY started_at",
                trace_id,
                tenant_id,
            )
        return tuple(_row_to_span(row) for row in rows)
