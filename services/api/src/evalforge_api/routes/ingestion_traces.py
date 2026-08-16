"""Trace ingestion endpoints (create, finalize, view).

Span-batch ingestion lives in ``evalforge_api.routes.ingestion_spans``
to keep this module within the modularity line ceiling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field

from evalforge_api.application import trace_service
from evalforge_api.domain.ingestion import compute_request_fingerprint
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from evalforge_api.ports.traces import TraceRecord
from evalforge_api.routes.ingestion_error_mapping import raise_as_http
from evalforge_api.security.dependencies import get_ingestion_repositories, get_tenant_context

router = APIRouter(prefix="/tenants/{tenant_id}/traces", tags=["ingestion"])

_IdempotencyKeyHeader = Header(..., alias="Idempotency-Key", min_length=1, max_length=200)


class TraceCreateRequest(BaseModel):
    run_id: UUID
    source: str = Field(min_length=1, max_length=200)
    provider_trace_id: str | None = Field(default=None, max_length=200)
    correlation_id: str | None = Field(default=None, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = Field(default="trace-v1", max_length=50)


class TraceFinalizeRequest(BaseModel):
    started_at: datetime | None = None
    ended_at: datetime | None = None


class TraceResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    run_id: UUID
    status: str
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

    @classmethod
    def from_record(cls, trace: TraceRecord) -> TraceResponse:
        return cls(
            id=trace.id,
            tenant_id=trace.tenant_id,
            workspace_id=trace.workspace_id,
            run_id=trace.run_id,
            status=trace.status.value,
            source=trace.source,
            provider_trace_id=trace.provider_trace_id,
            correlation_id=trace.correlation_id,
            started_at=trace.started_at,
            ended_at=trace.ended_at,
            metadata=trace.metadata,
            schema_version=trace.schema_version,
            created_by=trace.created_by,
            created_at=trace.created_at,
            finalized_at=trace.finalized_at,
        )


@router.post("", response_model=TraceResponse)
async def post_create_trace(
    tenant_id: UUID,
    body: TraceCreateRequest,
    response: Response,
    idempotency_key: str = _IdempotencyKeyHeader,
    context: TenantContext = Depends(get_tenant_context),
    ingestion_repositories: IngestionRepositories = Depends(get_ingestion_repositories),
) -> TraceResponse:
    del tenant_id
    try:
        trace, created = await trace_service.create_trace(
            context=context,
            run_id=body.run_id,
            source=body.source,
            provider_trace_id=body.provider_trace_id,
            correlation_id=body.correlation_id,
            metadata=body.metadata,
            schema_version=body.schema_version,
            idempotency_key=idempotency_key,
            request_fingerprint=compute_request_fingerprint(body.model_dump(mode="json")),
            ingestion_repositories=ingestion_repositories,
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    response.status_code = 201 if created else 200
    return TraceResponse.from_record(trace)


@router.post("/{trace_id}/finalize", response_model=TraceResponse)
async def post_finalize_trace(
    tenant_id: UUID,
    trace_id: UUID,
    body: TraceFinalizeRequest,
    idempotency_key: str = _IdempotencyKeyHeader,
    context: TenantContext = Depends(get_tenant_context),
    ingestion_repositories: IngestionRepositories = Depends(get_ingestion_repositories),
) -> TraceResponse:
    del tenant_id
    try:
        trace, _created = await trace_service.finalize_trace(
            context=context,
            trace_id=trace_id,
            started_at=body.started_at,
            ended_at=body.ended_at,
            idempotency_key=idempotency_key,
            request_fingerprint=compute_request_fingerprint(body.model_dump(mode="json")),
            ingestion_repositories=ingestion_repositories,
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return TraceResponse.from_record(trace)


@router.get("/{trace_id}", response_model=TraceResponse)
async def get_trace_route(
    tenant_id: UUID,
    trace_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    ingestion_repositories: IngestionRepositories = Depends(get_ingestion_repositories),
) -> TraceResponse:
    del tenant_id
    try:
        trace = await trace_service.get_trace(
            context=context, trace_id=trace_id, ingestion_repositories=ingestion_repositories
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return TraceResponse.from_record(trace)
