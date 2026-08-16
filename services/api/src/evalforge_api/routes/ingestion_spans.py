"""Span-batch ingestion and listing endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from evalforge_api.application import span_service
from evalforge_api.domain.ingestion import MAX_SPANS_PER_BATCH, compute_request_fingerprint
from evalforge_api.domain.ingestion_enums import SpanKind, SpanStatus
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from evalforge_api.ports.traces import SpanInput, SpanRecord
from evalforge_api.routes.ingestion_error_mapping import raise_as_http
from evalforge_api.security.dependencies import (
    get_evaluation_repositories,
    get_ingestion_repositories,
    get_tenant_context,
)

router = APIRouter(prefix="/tenants/{tenant_id}/traces/{trace_id}/spans", tags=["ingestion"])

_IdempotencyKeyHeader = Header(..., alias="Idempotency-Key", min_length=1, max_length=200)


class SpanItem(BaseModel):
    span_id: str = Field(min_length=1, max_length=200, description="Caller-assigned span id.")
    parent_span_id: str | None = Field(default=None, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    span_kind: SpanKind
    status: SpanStatus = SpanStatus.OK
    error_message: str | None = Field(default=None, max_length=2000)
    started_at: datetime
    ended_at: datetime | None = None
    model_version_id: UUID | None = None
    retrieval_config_version_id: UUID | None = None
    tool_definition_version_id: UUID | None = None
    workflow_version_id: UUID | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    input_artifact_version_id: UUID | None = None
    output_artifact_version_id: UUID | None = None
    token_count_input: int | None = Field(default=None, ge=0)
    token_count_output: int | None = Field(default=None, ge=0)
    cost_amount: Decimal | None = None
    cost_currency: str | None = Field(default=None, max_length=10)

    def to_domain(self) -> SpanInput:
        return SpanInput(
            provider_span_id=self.span_id,
            provider_parent_span_id=self.parent_span_id,
            name=self.name,
            span_kind=self.span_kind,
            status=self.status,
            error_message=self.error_message,
            started_at=self.started_at,
            ended_at=self.ended_at,
            model_version_id=self.model_version_id,
            retrieval_config_version_id=self.retrieval_config_version_id,
            tool_definition_version_id=self.tool_definition_version_id,
            workflow_version_id=self.workflow_version_id,
            attributes=self.attributes,
            input_artifact_version_id=self.input_artifact_version_id,
            output_artifact_version_id=self.output_artifact_version_id,
            token_count_input=self.token_count_input,
            token_count_output=self.token_count_output,
            cost_amount=self.cost_amount,
            cost_currency=self.cost_currency,
        )


class SpanBatchRequest(BaseModel):
    spans: list[SpanItem] = Field(min_length=1, max_length=MAX_SPANS_PER_BATCH)


class SpanResponse(BaseModel):
    id: UUID
    trace_id: UUID
    parent_span_id: UUID | None
    provider_span_id: str | None
    name: str
    span_kind: str
    status: str
    error_message: str | None
    started_at: datetime
    ended_at: datetime | None
    attributes: dict[str, Any]
    token_count_input: int | None
    token_count_output: int | None
    cost_amount: Decimal | None
    cost_currency: str | None
    created_at: datetime

    @classmethod
    def from_record(cls, span: SpanRecord) -> SpanResponse:
        return cls(
            id=span.id,
            trace_id=span.trace_id,
            parent_span_id=span.parent_span_id,
            provider_span_id=span.provider_span_id,
            name=span.name,
            span_kind=span.span_kind.value,
            status=span.status.value,
            error_message=span.error_message,
            started_at=span.started_at,
            ended_at=span.ended_at,
            attributes=span.attributes,
            token_count_input=span.token_count_input,
            token_count_output=span.token_count_output,
            cost_amount=span.cost_amount,
            cost_currency=span.cost_currency,
            created_at=span.created_at,
        )


@router.post("", response_model=list[SpanResponse])
async def post_ingest_spans(
    tenant_id: UUID,
    trace_id: UUID,
    body: SpanBatchRequest,
    idempotency_key: str = _IdempotencyKeyHeader,
    context: TenantContext = Depends(get_tenant_context),
    evaluation_repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
    ingestion_repositories: IngestionRepositories = Depends(get_ingestion_repositories),
) -> list[SpanResponse]:
    del tenant_id
    try:
        records, _created = await span_service.ingest_spans(
            context=context,
            trace_id=trace_id,
            spans=tuple(item.to_domain() for item in body.spans),
            idempotency_key=idempotency_key,
            request_fingerprint=compute_request_fingerprint(body.model_dump(mode="json")),
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return [SpanResponse.from_record(span) for span in records]


@router.get("", response_model=list[SpanResponse])
async def get_spans_route(
    tenant_id: UUID,
    trace_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    ingestion_repositories: IngestionRepositories = Depends(get_ingestion_repositories),
) -> list[SpanResponse]:
    del tenant_id
    try:
        records = await span_service.list_spans(
            context=context, trace_id=trace_id, ingestion_repositories=ingestion_repositories
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return [SpanResponse.from_record(span) for span in records]
