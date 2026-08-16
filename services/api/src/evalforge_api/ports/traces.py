"""Ports for canonical trace and span ingestion.

A trace is appendable while ``INGESTING`` and immutable once
``FINALIZED``. Spans carry a caller-assigned ``provider_span_id`` (the
OpenTelemetry-or-similar external identity) alongside our own
server-generated canonical ``id``, so batches can express parent/child
relationships before the canonical IDs exist — see
``evalforge_api.domain.ingestion`` for batch-size and immutability
rules and ``ARCHITECTURE.md`` for the OpenTelemetry-interoperability
boundary this separation preserves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from evalforge_api.domain.ingestion_enums import SpanKind, SpanStatus, TraceStatus


@dataclass(frozen=True, slots=True)
class TraceRecord:
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    run_id: UUID
    status: TraceStatus
    source: str
    provider_trace_id: str | None
    correlation_id: str | None
    started_at: datetime | None
    ended_at: datetime | None
    metadata: dict[str, Any]
    schema_version: str
    created_by: UUID
    created_at: datetime
    finalized_at: datetime | None


@dataclass(frozen=True, slots=True)
class SpanInput:
    """One span within an ingestion batch."""

    provider_span_id: str
    provider_parent_span_id: str | None
    name: str
    span_kind: SpanKind
    status: SpanStatus
    error_message: str | None
    started_at: datetime
    ended_at: datetime | None
    model_version_id: UUID | None
    retrieval_config_version_id: UUID | None
    tool_definition_version_id: UUID | None
    workflow_version_id: UUID | None
    attributes: dict[str, Any]
    input_artifact_version_id: UUID | None
    output_artifact_version_id: UUID | None
    token_count_input: int | None
    token_count_output: int | None
    cost_amount: Decimal | None
    cost_currency: str | None


@dataclass(frozen=True, slots=True)
class SpanRecord:
    id: UUID
    tenant_id: UUID
    trace_id: UUID
    batch_id: UUID
    parent_span_id: UUID | None
    provider_span_id: str | None
    name: str
    span_kind: SpanKind
    status: SpanStatus
    error_message: str | None
    started_at: datetime
    ended_at: datetime | None
    model_version_id: UUID | None
    retrieval_config_version_id: UUID | None
    tool_definition_version_id: UUID | None
    workflow_version_id: UUID | None
    attributes: dict[str, Any]
    input_artifact_version_id: UUID | None
    output_artifact_version_id: UUID | None
    token_count_input: int | None
    token_count_output: int | None
    cost_amount: Decimal | None
    cost_currency: str | None
    created_by: UUID
    created_at: datetime


class TraceRepository(Protocol):
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
    ) -> tuple[TraceRecord, bool]: ...

    async def get_trace(self, *, tenant_id: UUID, trace_id: UUID) -> TraceRecord | None: ...

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
    ) -> tuple[TraceRecord, bool]: ...


class SpanRepository(Protocol):
    async def ingest_batch(
        self,
        *,
        tenant_id: UUID,
        trace_id: UUID,
        spans: tuple[SpanInput, ...],
        created_by: UUID,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[tuple[SpanRecord, ...], bool]: ...

    async def list_for_trace(
        self, *, tenant_id: UUID, trace_id: UUID
    ) -> tuple[SpanRecord, ...]: ...
