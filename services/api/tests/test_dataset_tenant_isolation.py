"""Cross-tenant read and lifecycle isolation for datasets and test cases.

Bulk-transfer paths (export, import, clone) and the database-level
provenance foreign keys are covered by
``test_dataset_transfer_isolation.py``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from dataset_fixtures import (
    BuildContext,
    CreateTenant,
    CreateUser,
    add_test_case,
    bootstrap_two_tenants,
)
from evalforge_api.application import dataset_service, test_case_service
from evalforge_api.application.dataset_errors import DatasetNotFoundError, TestCaseNotFoundError
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


async def test_tenant_a_cannot_read_tenant_bs_dataset(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    tenant_a, tenant_b = await bootstrap_two_tenants(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
    )
    with pytest.raises(DatasetNotFoundError):
        await dataset_service.get_dataset(
            context=tenant_a.context,
            dataset_id=tenant_b.dataset_id,
            repositories=evaluation_repositories,
        )


async def test_listing_datasets_never_includes_another_tenants_rows(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    tenant_a, _ = await bootstrap_two_tenants(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
    )
    listed = await dataset_service.list_datasets(
        context=tenant_a.context, repositories=evaluation_repositories
    )
    assert {dataset.id for dataset in listed} == {tenant_a.dataset_id}


async def test_tenant_a_cannot_update_tenant_bs_dataset(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    tenant_a, tenant_b = await bootstrap_two_tenants(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
    )
    with pytest.raises(DatasetNotFoundError):
        await dataset_service.update_dataset(
            context=tenant_a.context,
            dataset_id=tenant_b.dataset_id,
            name="Hijacked",
            repositories=evaluation_repositories,
        )
    untouched = await dataset_service.get_dataset(
        context=tenant_b.context,
        dataset_id=tenant_b.dataset_id,
        repositories=evaluation_repositories,
    )
    assert untouched.name == "Tenant B private dataset"
    assert untouched.updated_by is None


async def test_tenant_a_cannot_archive_tenant_bs_dataset(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    tenant_a, tenant_b = await bootstrap_two_tenants(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
    )
    with pytest.raises(DatasetNotFoundError):
        await dataset_service.archive_dataset(
            context=tenant_a.context,
            dataset_id=tenant_b.dataset_id,
            repositories=evaluation_repositories,
        )
    untouched = await dataset_service.get_dataset(
        context=tenant_b.context,
        dataset_id=tenant_b.dataset_id,
        repositories=evaluation_repositories,
    )
    assert untouched.archived_at is None


async def test_tenant_a_cannot_read_or_archive_tenant_bs_test_case(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    tenant_a, tenant_b = await bootstrap_two_tenants(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
    )
    version_b = await add_test_case(
        fixture=tenant_b, repositories=evaluation_repositories, content={"input": "tenant b only"}
    )
    with pytest.raises(TestCaseNotFoundError):
        await test_case_service.get_test_case(
            context=tenant_a.context,
            test_case_id=version_b.test_case_id,
            repositories=evaluation_repositories,
        )
    with pytest.raises(TestCaseNotFoundError):
        await test_case_service.get_test_case_history(
            context=tenant_a.context,
            test_case_id=version_b.test_case_id,
            repositories=evaluation_repositories,
        )
    with pytest.raises(TestCaseNotFoundError):
        await test_case_service.archive_test_case(
            context=tenant_a.context,
            test_case_id=version_b.test_case_id,
            repositories=evaluation_repositories,
        )
    reread = await test_case_service.get_test_case(
        context=tenant_b.context,
        test_case_id=version_b.test_case_id,
        repositories=evaluation_repositories,
    )
    assert reread.archived_at is None


async def test_listing_tenant_bs_test_cases_from_tenant_a_returns_nothing(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    tenant_a, tenant_b = await bootstrap_two_tenants(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
    )
    await add_test_case(
        fixture=tenant_b, repositories=evaluation_repositories, content={"input": "tenant b only"}
    )
    listed = await test_case_service.list_test_cases(
        context=tenant_a.context,
        dataset_id=tenant_b.dataset_id,
        status=None,
        repositories=evaluation_repositories,
    )
    random_listing = await test_case_service.list_test_cases(
        context=tenant_a.context,
        dataset_id=uuid4(),
        status=None,
        repositories=evaluation_repositories,
    )
    assert listed == ()
    assert listed == random_listing
