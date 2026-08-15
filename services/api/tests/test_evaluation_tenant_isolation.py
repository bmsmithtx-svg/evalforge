from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import asyncpg
import pytest

from evalforge_api.adapters.dataset_snapshot_repository import SnapshotNotDraftError
from evalforge_api.application import (
    artifact_service,
    dataset_service,
    versioned_resource_service,
    workspace_service,
)
from evalforge_api.domain.enums import TenantRole
from evalforge_api.domain.evaluation_enums import ResourceKind
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.settings import Settings

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]

_TENANT_OWNED_TABLES = (
    "workspaces",
    "evaluation_targets",
    "versioned_resources",
    "versioned_resource_versions",
    "datasets",
    "test_cases",
    "test_case_versions",
    "dataset_snapshots",
    "dataset_snapshot_items",
    "artifacts",
    "artifact_versions",
)


async def _bootstrap_tenant(
    *,
    repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    slug: str,
    email: str,
) -> tuple[TenantContext, UUID]:
    tenant_id = await create_tenant(slug)
    user_id = await create_user(email)
    admin_context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.TENANT_ADMIN
    )
    workspace = await workspace_service.create_workspace(
        context=admin_context, slug="ws", name="Workspace", repositories=repositories
    )
    engineer_context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.EVALUATION_ENGINEER
    )
    return engineer_context, workspace.id


async def test_tenant_a_cannot_read_tenant_bs_versioned_resource(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context_a, workspace_a = await _bootstrap_tenant(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="a@example.com",
    )
    context_b, workspace_b = await _bootstrap_tenant(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-b",
        email="b@example.com",
    )
    resource_b = await versioned_resource_service.create_resource(
        context=context_b,
        workspace_id=workspace_b,
        kind=ResourceKind.MODEL_CONFIG,
        name="tenant-b-model",
        repositories=evaluation_repositories,
    )

    # Guessing or substituting Tenant B's real resource ID under
    # Tenant A's own verified context must not return Tenant B's data.
    result = await evaluation_repositories.versioned_resources.get_resource(
        tenant_id=context_a.tenant_id, resource_id=resource_b.id
    )
    assert result is None


async def test_tenant_a_cannot_attach_tenant_bs_test_case_version_to_its_own_snapshot(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context_a, workspace_a = await _bootstrap_tenant(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="a2@example.com",
    )
    context_b, workspace_b = await _bootstrap_tenant(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-b",
        email="b2@example.com",
    )

    dataset_a = await dataset_service.create_dataset(
        context=context_a, workspace_id=workspace_a, name="A", repositories=evaluation_repositories
    )
    dataset_b = await dataset_service.create_dataset(
        context=context_b, workspace_id=workspace_b, name="B", repositories=evaluation_repositories
    )
    case_b = await dataset_service.create_test_case(
        context=context_b,
        dataset_id=dataset_b.id,
        external_key=None,
        repositories=evaluation_repositories,
    )
    version_b = await dataset_service.create_test_case_version(
        context=context_b,
        test_case_id=case_b.id,
        content={"input": "tenant-b-only"},
        repositories=evaluation_repositories,
    )
    snapshot_a = await evaluation_repositories.snapshots.create_draft(
        tenant_id=context_a.tenant_id, dataset_id=dataset_a.id, created_by=context_a.user_id
    )

    # Two independent layers reject this: RLS hides Tenant B's
    # test-case version from the trigger's own lookup (so it sees no
    # matching dataset and raises), and even if RLS were somehow
    # bypassed the composite tenant foreign key on this column would
    # still reject a genuinely cross-tenant reference.
    with pytest.raises(SnapshotNotDraftError):
        await evaluation_repositories.snapshots.add_item(
            tenant_id=context_a.tenant_id,
            snapshot_id=snapshot_a.id,
            test_case_version_id=version_b.id,
            sequence_index=0,
        )


async def test_tenant_a_cannot_reference_tenant_bs_artifact_version_as_lineage(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context_a, workspace_a = await _bootstrap_tenant(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="a3@example.com",
    )
    context_b, workspace_b = await _bootstrap_tenant(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-b",
        email="b3@example.com",
    )
    artifact_b = await artifact_service.create_artifact(
        context=context_b,
        workspace_id=workspace_b,
        media_type="text/plain",
        purpose="report",
        repositories=evaluation_repositories,
    )
    version_b = await artifact_service.store_artifact_version(
        context=context_b,
        artifact_id=artifact_b.id,
        body=b"tenant-b-bytes",
        content_type="text/plain",
        derived_from_artifact_version_id=None,
        repositories=evaluation_repositories,
    )
    artifact_a = await artifact_service.create_artifact(
        context=context_a,
        workspace_id=workspace_a,
        media_type="text/plain",
        purpose="report",
        repositories=evaluation_repositories,
    )

    # RLS hides Tenant B's version from the lineage-validation
    # trigger's own lookup, so it raises rather than the composite
    # foreign key ever being reached — and that foreign key remains a
    # second, independent barrier if RLS were ever bypassed.
    with pytest.raises(asyncpg.exceptions.RaiseError):
        await evaluation_repositories.artifacts.create_artifact_version(
            tenant_id=context_a.tenant_id,
            artifact_id=artifact_a.id,
            version_number=1,
            content_hash="deadbeef",
            hash_algorithm="sha256",
            byte_size=1,
            content_type="text/plain",
            storage_key=f"tenants/{context_a.tenant_id}/artifacts/{artifact_a.id}/versions/1-x",
            derived_from_artifact_version_id=version_b.id,
            created_by=context_a.user_id,
        )


async def test_substituting_a_random_uuid_does_not_leak_existence_of_another_tenants_row(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context_a, workspace_a = await _bootstrap_tenant(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="a4@example.com",
    )
    dataset = await dataset_service.create_dataset(
        context=context_a, workspace_id=workspace_a, name="A", repositories=evaluation_repositories
    )
    real_result = await evaluation_repositories.datasets.get_dataset(
        tenant_id=context_a.tenant_id, dataset_id=dataset.id
    )
    random_result = await evaluation_repositories.datasets.get_dataset(
        tenant_id=context_a.tenant_id, dataset_id=uuid4()
    )
    assert real_result is not None
    assert random_result is None


async def test_direct_database_access_with_no_tenant_context_exposes_no_rows(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
    test_settings: Settings,
) -> None:
    await _bootstrap_tenant(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="a5@example.com",
    )

    connection = await asyncpg.connect(dsn=str(test_settings.app_database_url))
    try:
        for table in _TENANT_OWNED_TABLES:
            rows = await connection.fetch(f"SELECT * FROM {table}")  # noqa: S608
            assert rows == [], f"{table} exposed rows with no RLS session context"
    finally:
        await connection.close()
