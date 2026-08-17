"""Cross-tenant isolation of the bulk-transfer paths.

Export, import, and clone all move *content* rather than reading a
single row, so each is checked separately — and the last two tests go
below the application layer to prove the database refuses a forged
cross-tenant provenance reference even when a repository is called
directly.
"""

from __future__ import annotations

import asyncpg
import pytest

from dataset_fixtures import (
    BuildContext,
    CreateTenant,
    CreateUser,
    add_test_case,
    bootstrap_two_tenants,
)
from evalforge_api.application import (
    dataset_clone_service,
    dataset_export_service,
    dataset_import_service,
    dataset_service,
)
from evalforge_api.application.dataset_errors import DatasetNotFoundError
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


async def test_tenant_a_cannot_export_tenant_bs_dataset(
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
        fixture=tenant_b,
        repositories=evaluation_repositories,
        content={"input": "tenant b confidential"},
    )
    with pytest.raises(DatasetNotFoundError):
        await dataset_export_service.export_dataset(
            context=tenant_a.context,
            dataset_id=tenant_b.dataset_id,
            snapshot_id=None,
            export_format="jsonl",
            repositories=evaluation_repositories,
        )


async def test_tenant_a_cannot_import_into_tenant_bs_dataset(
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
        await dataset_import_service.import_test_cases(
            context=tenant_a.context,
            dataset_id=tenant_b.dataset_id,
            document='{"input": "injected"}\n',
            import_format="jsonl",
            repositories=evaluation_repositories,
        )
    cases = await evaluation_repositories.datasets.list_test_cases(
        tenant_id=tenant_b.tenant_id, dataset_id=tenant_b.dataset_id, status=None
    )
    assert cases == ()


async def test_tenant_a_cannot_clone_tenant_bs_dataset(
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
    with pytest.raises(DatasetNotFoundError):
        await dataset_clone_service.clone_dataset(
            context=tenant_a.context,
            source_dataset_id=tenant_b.dataset_id,
            source_snapshot_id=None,
            new_name="Exfiltrated",
            repositories=evaluation_repositories,
        )
    tenant_a_datasets = await dataset_service.list_datasets(
        context=tenant_a.context, repositories=evaluation_repositories
    )
    assert {dataset.id for dataset in tenant_a_datasets} == {tenant_a.dataset_id}


async def test_a_clone_provenance_column_cannot_reference_another_tenants_dataset(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    """The database refuses a cross-tenant provenance reference even
    when the repository is called directly, because the foreign key is
    composite on ``(id, tenant_id)``."""
    tenant_a, tenant_b = await bootstrap_two_tenants(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
    )
    with pytest.raises(asyncpg.exceptions.ForeignKeyViolationError):
        await evaluation_repositories.datasets.create_dataset(
            tenant_id=tenant_a.tenant_id,
            workspace_id=tenant_a.workspace_id,
            name="Forged lineage",
            description=None,
            tags=(),
            metadata={},
            source="cloned",
            cloned_from_dataset_id=tenant_b.dataset_id,
            cloned_from_snapshot_id=None,
            created_by=tenant_a.user_id,
        )


async def test_a_test_case_cannot_claim_another_tenants_case_as_its_source(
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
    with pytest.raises(asyncpg.exceptions.ForeignKeyViolationError):
        await evaluation_repositories.datasets.create_test_case(
            tenant_id=tenant_a.tenant_id,
            dataset_id=tenant_a.dataset_id,
            external_key="forged",
            source="cloned",
            source_test_case_id=version_b.test_case_id,
            import_batch_id=None,
            created_by=tenant_a.user_id,
        )
