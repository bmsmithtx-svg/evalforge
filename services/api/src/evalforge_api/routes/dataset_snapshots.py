"""Dataset-snapshot endpoints: draft creation, membership,
finalization, reads, and comparison.

Snapshot comparison is exposed as ``GET /snapshot-comparisons`` with
both IDs as query parameters rather than as a path under
``/snapshots/{id}``, so it cannot collide with the snapshot-by-ID route
and so neither snapshot is implied to be "the" subject of the request.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from evalforge_api.application import snapshot_comparison_service, snapshot_service
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.routes.dataset_error_mapping import raise_as_http
from evalforge_api.routes.dataset_response_models import (
    DatasetSnapshotItemResponse,
    DatasetSnapshotResponse,
)
from evalforge_api.security.dependencies import get_evaluation_repositories, get_tenant_context

router = APIRouter(prefix="/tenants/{tenant_id}", tags=["datasets"])


class SnapshotItemAddRequest(BaseModel):
    test_case_version_id: UUID
    sequence_index: int = Field(ge=0)


class SnapshotListResponse(BaseModel):
    snapshots: list[DatasetSnapshotResponse]


class SnapshotItemListResponse(BaseModel):
    snapshot_id: UUID
    items: list[DatasetSnapshotItemResponse]


class SnapshotComparisonResponse(BaseModel):
    left_snapshot_id: UUID
    right_snapshot_id: UUID
    added: list[UUID]
    removed: list[UUID]
    changed: list[dict[str, str | int]]
    unchanged: list[UUID]


@router.post("/datasets/{dataset_id}/snapshots", response_model=DatasetSnapshotResponse)
async def post_create_draft_snapshot(
    tenant_id: UUID,
    dataset_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> DatasetSnapshotResponse:
    del tenant_id  # resolved and verified by get_tenant_context
    try:
        snapshot = await snapshot_service.create_draft_snapshot(
            context=context, dataset_id=dataset_id, repositories=repositories
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return DatasetSnapshotResponse.from_record(snapshot)


@router.get("/datasets/{dataset_id}/snapshots", response_model=SnapshotListResponse)
async def get_list_snapshots(
    tenant_id: UUID,
    dataset_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> SnapshotListResponse:
    del tenant_id
    try:
        snapshots = await snapshot_service.list_snapshots(
            context=context, dataset_id=dataset_id, repositories=repositories
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return SnapshotListResponse(
        snapshots=[DatasetSnapshotResponse.from_record(item) for item in snapshots]
    )


@router.post("/snapshots/{snapshot_id}/items", status_code=201)
async def post_add_snapshot_item(
    tenant_id: UUID,
    snapshot_id: UUID,
    body: SnapshotItemAddRequest,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> dict[str, str]:
    del tenant_id
    try:
        await snapshot_service.add_test_case_version(
            context=context,
            snapshot_id=snapshot_id,
            test_case_version_id=body.test_case_version_id,
            sequence_index=body.sequence_index,
            repositories=repositories,
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return {"snapshot_id": str(snapshot_id), "outcome": "added"}


@router.post("/snapshots/{snapshot_id}/finalize", response_model=DatasetSnapshotResponse)
async def post_finalize_snapshot(
    tenant_id: UUID,
    snapshot_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> DatasetSnapshotResponse:
    del tenant_id
    try:
        snapshot = await snapshot_service.finalize_snapshot(
            context=context, snapshot_id=snapshot_id, repositories=repositories
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return DatasetSnapshotResponse.from_record(snapshot)


@router.get("/snapshots/{snapshot_id}", response_model=DatasetSnapshotResponse)
async def get_snapshot_route(
    tenant_id: UUID,
    snapshot_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> DatasetSnapshotResponse:
    del tenant_id
    try:
        snapshot = await snapshot_service.get_snapshot(
            context=context, snapshot_id=snapshot_id, repositories=repositories
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return DatasetSnapshotResponse.from_record(snapshot)


@router.get("/snapshots/{snapshot_id}/items", response_model=SnapshotItemListResponse)
async def get_snapshot_items(
    tenant_id: UUID,
    snapshot_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> SnapshotItemListResponse:
    del tenant_id
    try:
        items = await snapshot_service.list_snapshot_items(
            context=context, snapshot_id=snapshot_id, repositories=repositories
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return SnapshotItemListResponse(
        snapshot_id=snapshot_id,
        items=[DatasetSnapshotItemResponse.from_record(item) for item in items],
    )


@router.get("/snapshot-comparisons", response_model=SnapshotComparisonResponse)
async def get_compare_snapshots(
    tenant_id: UUID,
    left_snapshot_id: UUID = Query(...),
    right_snapshot_id: UUID = Query(...),
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> SnapshotComparisonResponse:
    del tenant_id
    try:
        result = await snapshot_comparison_service.compare_snapshots(
            context=context,
            left_snapshot_id=left_snapshot_id,
            right_snapshot_id=right_snapshot_id,
            repositories=repositories,
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return SnapshotComparisonResponse(
        left_snapshot_id=left_snapshot_id,
        right_snapshot_id=right_snapshot_id,
        added=list(result.added),
        removed=list(result.removed),
        changed=[
            {
                "test_case_id": str(test_case_id),
                "left_version_number": left_version,
                "right_version_number": right_version,
            }
            for test_case_id, left_version, right_version in result.changed
        ],
        unchanged=list(result.unchanged),
    )
