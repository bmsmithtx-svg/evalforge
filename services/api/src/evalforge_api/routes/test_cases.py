"""Test-case endpoints: create, list, read, version history, new
version, archive.

A content change is always a *new version* — there is deliberately no
PUT/PATCH that rewrites content, because a test-case version is
immutable evidence once a snapshot freezes it
(docs/REPRODUCIBILITY_CONTRACT.md).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from evalforge_api.application import test_case_service
from evalforge_api.domain.evaluation_enums import TestCaseStatus
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.routes.dataset_error_mapping import raise_as_http
from evalforge_api.routes.dataset_response_models import (
    TestCaseResponse,
    TestCaseVersionResponse,
)
from evalforge_api.security.dependencies import get_evaluation_repositories, get_tenant_context

router = APIRouter(prefix="/tenants/{tenant_id}", tags=["datasets"])

_MAX_EXTERNAL_KEY_LENGTH = 200


class TestCaseCreateRequest(BaseModel):
    external_key: str | None = Field(default=None, max_length=_MAX_EXTERNAL_KEY_LENGTH)
    content: dict[str, Any] | None = None


class TestCaseVersionCreateRequest(BaseModel):
    content: dict[str, Any]


class TestCaseListResponse(BaseModel):
    test_cases: list[TestCaseResponse]


class TestCaseHistoryResponse(BaseModel):
    test_case_id: UUID
    versions: list[TestCaseVersionResponse]


class TestCaseCreatedResponse(BaseModel):
    test_case: TestCaseResponse
    version: TestCaseVersionResponse | None


@router.post("/datasets/{dataset_id}/test-cases", response_model=TestCaseCreatedResponse)
async def post_create_test_case(
    tenant_id: UUID,
    dataset_id: UUID,
    body: TestCaseCreateRequest,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> TestCaseCreatedResponse:
    """Create a test case, and its first content version when
    ``content`` is supplied."""
    del tenant_id  # resolved and verified by get_tenant_context
    try:
        test_case = await test_case_service.create_test_case(
            context=context,
            dataset_id=dataset_id,
            external_key=body.external_key,
            repositories=repositories,
        )
        version = None
        if body.content is not None:
            version = await test_case_service.create_test_case_version(
                context=context,
                test_case_id=test_case.id,
                content=body.content,
                repositories=repositories,
            )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return TestCaseCreatedResponse(
        test_case=TestCaseResponse.from_record(test_case),
        version=TestCaseVersionResponse.from_record(version) if version is not None else None,
    )


@router.get("/datasets/{dataset_id}/test-cases", response_model=TestCaseListResponse)
async def get_list_test_cases(
    tenant_id: UUID,
    dataset_id: UUID,
    status: TestCaseStatus | None = Query(default=None),
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> TestCaseListResponse:
    del tenant_id
    try:
        test_cases = await test_case_service.list_test_cases(
            context=context, dataset_id=dataset_id, status=status, repositories=repositories
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return TestCaseListResponse(
        test_cases=[TestCaseResponse.from_record(case) for case in test_cases]
    )


@router.get("/test-cases/{test_case_id}", response_model=TestCaseResponse)
async def get_test_case_route(
    tenant_id: UUID,
    test_case_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> TestCaseResponse:
    del tenant_id
    try:
        test_case = await test_case_service.get_test_case(
            context=context, test_case_id=test_case_id, repositories=repositories
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return TestCaseResponse.from_record(test_case)


@router.get("/test-cases/{test_case_id}/versions", response_model=TestCaseHistoryResponse)
async def get_test_case_history(
    tenant_id: UUID,
    test_case_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> TestCaseHistoryResponse:
    del tenant_id
    try:
        versions = await test_case_service.get_test_case_history(
            context=context, test_case_id=test_case_id, repositories=repositories
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return TestCaseHistoryResponse(
        test_case_id=test_case_id,
        versions=[TestCaseVersionResponse.from_record(version) for version in versions],
    )


@router.post("/test-cases/{test_case_id}/versions", response_model=TestCaseVersionResponse)
async def post_create_test_case_version(
    tenant_id: UUID,
    test_case_id: UUID,
    body: TestCaseVersionCreateRequest,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> TestCaseVersionResponse:
    del tenant_id
    try:
        version = await test_case_service.create_test_case_version(
            context=context,
            test_case_id=test_case_id,
            content=body.content,
            repositories=repositories,
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return TestCaseVersionResponse.from_record(version)


@router.post("/test-cases/{test_case_id}/archive", response_model=TestCaseResponse)
async def post_archive_test_case(
    tenant_id: UUID,
    test_case_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> TestCaseResponse:
    del tenant_id
    try:
        test_case = await test_case_service.archive_test_case(
            context=context, test_case_id=test_case_id, repositories=repositories
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return TestCaseResponse.from_record(test_case)
