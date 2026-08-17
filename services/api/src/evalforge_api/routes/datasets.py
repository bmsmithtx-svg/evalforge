"""Dataset lifecycle endpoints: create, list, read, update, archive.

Thin delivery layer: authenticate, resolve tenant context, validate
transport shape, call one ``evalforge_api.application.dataset_service``
function, and translate errors through ``raise_as_http``
(docs/ARCHITECTURE.md).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from evalforge_api.application import dataset_service
from evalforge_api.domain.evaluation_enums import DatasetStatus
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.routes.dataset_error_mapping import raise_as_http
from evalforge_api.routes.dataset_response_models import DatasetResponse
from evalforge_api.security.dependencies import get_evaluation_repositories, get_tenant_context

router = APIRouter(prefix="/tenants/{tenant_id}/datasets", tags=["datasets"])

_MAX_NAME_LENGTH = 200
_MAX_DESCRIPTION_LENGTH = 4_000
_MAX_TAGS = 50


class DatasetCreateRequest(BaseModel):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=_MAX_NAME_LENGTH)
    description: str | None = Field(default=None, max_length=_MAX_DESCRIPTION_LENGTH)
    tags: list[str] = Field(default_factory=list, max_length=_MAX_TAGS)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetUpdateRequest(BaseModel):
    """Every field is optional; omitted fields are left unchanged."""

    name: str | None = Field(default=None, min_length=1, max_length=_MAX_NAME_LENGTH)
    description: str | None = Field(default=None, max_length=_MAX_DESCRIPTION_LENGTH)
    tags: list[str] | None = Field(default=None, max_length=_MAX_TAGS)
    metadata: dict[str, Any] | None = None


class DatasetListResponse(BaseModel):
    datasets: list[DatasetResponse]


@router.post("", response_model=DatasetResponse, status_code=201)
async def post_create_dataset(
    tenant_id: UUID,
    body: DatasetCreateRequest,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> DatasetResponse:
    del tenant_id  # resolved and verified by get_tenant_context
    try:
        dataset = await dataset_service.create_dataset(
            context=context,
            workspace_id=body.workspace_id,
            name=body.name,
            description=body.description,
            tags=tuple(body.tags),
            metadata=body.metadata,
            repositories=repositories,
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return DatasetResponse.from_record(dataset)


@router.get("", response_model=DatasetListResponse)
async def get_list_datasets(
    tenant_id: UUID,
    workspace_id: UUID | None = Query(default=None),
    status: DatasetStatus | None = Query(default=None),
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> DatasetListResponse:
    del tenant_id
    try:
        datasets = await dataset_service.list_datasets(
            context=context, workspace_id=workspace_id, status=status, repositories=repositories
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return DatasetListResponse(
        datasets=[DatasetResponse.from_record(dataset) for dataset in datasets]
    )


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset_route(
    tenant_id: UUID,
    dataset_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> DatasetResponse:
    del tenant_id
    try:
        dataset = await dataset_service.get_dataset(
            context=context, dataset_id=dataset_id, repositories=repositories
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return DatasetResponse.from_record(dataset)


@router.patch("/{dataset_id}", response_model=DatasetResponse)
async def patch_update_dataset(
    tenant_id: UUID,
    dataset_id: UUID,
    body: DatasetUpdateRequest,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> DatasetResponse:
    del tenant_id
    try:
        dataset = await dataset_service.update_dataset(
            context=context,
            dataset_id=dataset_id,
            name=body.name,
            description=body.description,
            tags=tuple(body.tags) if body.tags is not None else None,
            metadata=body.metadata,
            repositories=repositories,
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return DatasetResponse.from_record(dataset)


@router.post("/{dataset_id}/archive", response_model=DatasetResponse)
async def post_archive_dataset(
    tenant_id: UUID,
    dataset_id: UUID,
    response: Response,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> DatasetResponse:
    del tenant_id
    try:
        dataset = await dataset_service.archive_dataset(
            context=context, dataset_id=dataset_id, repositories=repositories
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    response.status_code = 200
    return DatasetResponse.from_record(dataset)
