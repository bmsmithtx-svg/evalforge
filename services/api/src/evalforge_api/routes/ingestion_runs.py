"""Run ingestion endpoints.

Thin delivery layer: authenticate, resolve tenant context, validate
transport shape, call ``evalforge_api.application.run_service``, and
translate results/errors into standardized responses
(docs/ARCHITECTURE.md).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field

from evalforge_api.application import run_service
from evalforge_api.domain.ingestion import compute_request_fingerprint
from evalforge_api.domain.ingestion_enums import RunStatus
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from evalforge_api.ports.runs import RunRecord
from evalforge_api.routes.ingestion_error_mapping import raise_as_http
from evalforge_api.security.dependencies import (
    get_evaluation_repositories,
    get_ingestion_repositories,
    get_tenant_context,
)

router = APIRouter(prefix="/tenants/{tenant_id}/runs", tags=["ingestion"])

_IdempotencyKeyHeader = Header(..., alias="Idempotency-Key", min_length=1, max_length=200)


class RunCreateRequest(BaseModel):
    workspace_id: UUID
    evaluation_target_id: UUID | None = None
    model_version_id: UUID | None = None
    prompt_version_id: UUID | None = None
    retrieval_config_version_id: UUID | None = None
    workflow_version_id: UUID | None = None
    pricing_version_id: UUID | None = None
    tool_definition_version_ids: list[UUID] = Field(default_factory=list, max_length=50)
    source: str = Field(min_length=1, max_length=200)
    correlation_id: str | None = Field(default=None, max_length=200)
    started_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = Field(default="run-v1", max_length=50)


class RunFinalizeRequest(BaseModel):
    status: Literal["completed", "failed", "canceled"]
    ended_at: datetime
    metadata: dict[str, Any] | None = None


class RunResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    evaluation_target_id: UUID | None
    model_version_id: UUID | None
    prompt_version_id: UUID | None
    retrieval_config_version_id: UUID | None
    workflow_version_id: UUID | None
    pricing_version_id: UUID | None
    status: str
    source: str
    correlation_id: str | None
    started_at: datetime
    ended_at: datetime | None
    metadata: dict[str, Any]
    schema_version: str
    created_by: UUID
    created_at: datetime
    finalized_at: datetime | None

    @classmethod
    def from_record(cls, run: RunRecord) -> RunResponse:
        return cls(
            id=run.id,
            tenant_id=run.tenant_id,
            workspace_id=run.workspace_id,
            evaluation_target_id=run.evaluation_target_id,
            model_version_id=run.model_version_id,
            prompt_version_id=run.prompt_version_id,
            retrieval_config_version_id=run.retrieval_config_version_id,
            workflow_version_id=run.workflow_version_id,
            pricing_version_id=run.pricing_version_id,
            status=run.status.value,
            source=run.source,
            correlation_id=run.correlation_id,
            started_at=run.started_at,
            ended_at=run.ended_at,
            metadata=run.metadata,
            schema_version=run.schema_version,
            created_by=run.created_by,
            created_at=run.created_at,
            finalized_at=run.finalized_at,
        )


@router.post("", response_model=RunResponse)
async def post_create_run(
    tenant_id: UUID,
    body: RunCreateRequest,
    response: Response,
    idempotency_key: str = _IdempotencyKeyHeader,
    context: TenantContext = Depends(get_tenant_context),
    evaluation_repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
    ingestion_repositories: IngestionRepositories = Depends(get_ingestion_repositories),
) -> RunResponse:
    del tenant_id  # resolved and verified by get_tenant_context
    try:
        run, created = await run_service.create_run(
            context=context,
            workspace_id=body.workspace_id,
            evaluation_target_id=body.evaluation_target_id,
            model_version_id=body.model_version_id,
            prompt_version_id=body.prompt_version_id,
            retrieval_config_version_id=body.retrieval_config_version_id,
            workflow_version_id=body.workflow_version_id,
            pricing_version_id=body.pricing_version_id,
            tool_definition_version_ids=tuple(body.tool_definition_version_ids),
            source=body.source,
            correlation_id=body.correlation_id,
            started_at=body.started_at,
            metadata=body.metadata,
            schema_version=body.schema_version,
            idempotency_key=idempotency_key,
            request_fingerprint=compute_request_fingerprint(body.model_dump(mode="json")),
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    response.status_code = 201 if created else 200
    return RunResponse.from_record(run)


@router.post("/{run_id}/finalize", response_model=RunResponse)
async def post_finalize_run(
    tenant_id: UUID,
    run_id: UUID,
    body: RunFinalizeRequest,
    idempotency_key: str = _IdempotencyKeyHeader,
    context: TenantContext = Depends(get_tenant_context),
    ingestion_repositories: IngestionRepositories = Depends(get_ingestion_repositories),
) -> RunResponse:
    del tenant_id
    try:
        run, created = await run_service.finalize_run(
            context=context,
            run_id=run_id,
            status=RunStatus(body.status),
            ended_at=body.ended_at,
            metadata=body.metadata,
            idempotency_key=idempotency_key,
            request_fingerprint=compute_request_fingerprint(body.model_dump(mode="json")),
            ingestion_repositories=ingestion_repositories,
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    del created  # finalize always returns 200; only creation distinguishes 201 vs 200
    return RunResponse.from_record(run)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run_route(
    tenant_id: UUID,
    run_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    ingestion_repositories: IngestionRepositories = Depends(get_ingestion_repositories),
) -> RunResponse:
    del tenant_id
    try:
        run = await run_service.get_run(
            context=context, run_id=run_id, ingestion_repositories=ingestion_repositories
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return RunResponse.from_record(run)
