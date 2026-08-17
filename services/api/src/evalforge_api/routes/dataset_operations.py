"""Dataset operations: clone, duplicate check, deterministic sampling
and splitting.

Sampling and splitting are stateless computations over a finalized
snapshot — nothing is persisted, so these are POST endpoints that
return a result rather than create a resource
(``evalforge_api.application.dataset_sampling_service`` explains why).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from evalforge_api.application import (
    dataset_clone_service,
    dataset_sampling_service,
    duplicate_detection_service,
)
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.domain.test_case_content import InvalidTestCaseContentError, TestCaseContent
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.routes.dataset_error_mapping import raise_as_http
from evalforge_api.routes.dataset_response_models import DatasetResponse
from evalforge_api.security.dependencies import get_evaluation_repositories, get_tenant_context

router = APIRouter(prefix="/tenants/{tenant_id}", tags=["datasets"])

_MAX_NAME_LENGTH = 200
_MAX_SPLIT_BUCKETS = 10


class DatasetCloneRequest(BaseModel):
    new_name: str = Field(min_length=1, max_length=_MAX_NAME_LENGTH)
    source_snapshot_id: UUID | None = None


class DuplicateCheckRequest(BaseModel):
    content: dict[str, Any]


class DuplicateCheckResponse(BaseModel):
    dataset_id: UUID
    duplicate_test_case_ids: list[UUID]


class SnapshotSampleRequest(BaseModel):
    sample_size: int = Field(ge=0)
    seed: str = Field(min_length=1, max_length=200)


class SnapshotSampleResponse(BaseModel):
    snapshot_id: UUID
    seed: str
    test_case_version_ids: list[UUID]


class SnapshotSplitRequest(BaseModel):
    ratios: dict[str, float] = Field(min_length=1, max_length=_MAX_SPLIT_BUCKETS)
    seed: str = Field(min_length=1, max_length=200)


class SnapshotSplitResponse(BaseModel):
    snapshot_id: UUID
    seed: str
    buckets: dict[str, list[UUID]]


@router.post("/datasets/{dataset_id}/clone", response_model=DatasetResponse, status_code=201)
async def post_clone_dataset(
    tenant_id: UUID,
    dataset_id: UUID,
    body: DatasetCloneRequest,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> DatasetResponse:
    del tenant_id  # resolved and verified by get_tenant_context
    try:
        clone = await dataset_clone_service.clone_dataset(
            context=context,
            source_dataset_id=dataset_id,
            source_snapshot_id=body.source_snapshot_id,
            new_name=body.new_name,
            repositories=repositories,
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return DatasetResponse.from_record(clone)


@router.post("/datasets/{dataset_id}/duplicate-check", response_model=DuplicateCheckResponse)
async def post_duplicate_check(
    tenant_id: UUID,
    dataset_id: UUID,
    body: DuplicateCheckRequest,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> DuplicateCheckResponse:
    del tenant_id
    try:
        content = TestCaseContent.from_json_dict(body.content)
        duplicates = await duplicate_detection_service.check_for_duplicates(
            context=context, dataset_id=dataset_id, content=content, repositories=repositories
        )
    except InvalidTestCaseContentError as exc:
        raise_as_http(exc)
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return DuplicateCheckResponse(dataset_id=dataset_id, duplicate_test_case_ids=list(duplicates))


@router.post("/snapshots/{snapshot_id}/sample", response_model=SnapshotSampleResponse)
async def post_sample_snapshot(
    tenant_id: UUID,
    snapshot_id: UUID,
    body: SnapshotSampleRequest,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> SnapshotSampleResponse:
    del tenant_id
    try:
        sampled = await dataset_sampling_service.sample_snapshot(
            context=context,
            snapshot_id=snapshot_id,
            sample_size=body.sample_size,
            seed=body.seed,
            repositories=repositories,
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return SnapshotSampleResponse(
        snapshot_id=snapshot_id, seed=body.seed, test_case_version_ids=list(sampled)
    )


@router.post("/snapshots/{snapshot_id}/split", response_model=SnapshotSplitResponse)
async def post_split_snapshot(
    tenant_id: UUID,
    snapshot_id: UUID,
    body: SnapshotSplitRequest,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> SnapshotSplitResponse:
    del tenant_id
    try:
        buckets = await dataset_sampling_service.split_snapshot(
            context=context,
            snapshot_id=snapshot_id,
            ratios=body.ratios,
            seed=body.seed,
            repositories=repositories,
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return SnapshotSplitResponse(
        snapshot_id=snapshot_id,
        seed=body.seed,
        buckets={name: list(members) for name, members in buckets.items()},
    )
