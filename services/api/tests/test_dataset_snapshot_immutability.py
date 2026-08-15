from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

import asyncpg
import pytest

from evalforge_api.adapters.dataset_snapshot_repository import SnapshotNotDraftError
from evalforge_api.application import dataset_service, snapshot_service, workspace_service
from evalforge_api.domain.enums import TenantRole
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.domain.versioning import ImmutableRecordError
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.settings import Settings

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]


async def _setup(
    *,
    repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    tenant_id: UUID,
    user_id: UUID,
) -> tuple[TenantContext, UUID]:
    admin_context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.TENANT_ADMIN
    )
    workspace = await workspace_service.create_workspace(
        context=admin_context, slug="ws", name="Workspace", repositories=repositories
    )
    engineer_context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.EVALUATION_ENGINEER
    )
    dataset = await dataset_service.create_dataset(
        context=engineer_context,
        workspace_id=workspace.id,
        name="Dataset A",
        repositories=repositories,
    )
    return engineer_context, dataset.id


async def test_finalized_snapshot_is_unchanged_after_dataset_evolves(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    tenant_id = await create_tenant("tenant-a")
    user_id = await create_user("engineer@example.com")
    context, dataset_id = await _setup(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        tenant_id=tenant_id,
        user_id=user_id,
    )

    # 1 & 2: create Dataset A's test cases and their first versions.
    case_one = await dataset_service.create_test_case(
        context=context,
        dataset_id=dataset_id,
        external_key="case-1",
        repositories=evaluation_repositories,
    )
    case_two = await dataset_service.create_test_case(
        context=context,
        dataset_id=dataset_id,
        external_key="case-2",
        repositories=evaluation_repositories,
    )
    case_one_v1 = await dataset_service.create_test_case_version(
        context=context,
        test_case_id=case_one.id,
        content={"input": "1 + 1", "expected": "2"},
        repositories=evaluation_repositories,
    )
    case_two_v1 = await dataset_service.create_test_case_version(
        context=context,
        test_case_id=case_two.id,
        content={"input": "2 + 2", "expected": "4"},
        repositories=evaluation_repositories,
    )

    # 3 & 4: build and finalize Snapshot 1; record its membership and hash.
    snapshot_one = await snapshot_service.create_draft_snapshot(
        context=context, dataset_id=dataset_id, repositories=evaluation_repositories
    )
    await snapshot_service.add_test_case_version(
        context=context,
        snapshot_id=snapshot_one.id,
        test_case_version_id=case_one_v1.id,
        sequence_index=0,
        repositories=evaluation_repositories,
    )
    await snapshot_service.add_test_case_version(
        context=context,
        snapshot_id=snapshot_one.id,
        test_case_version_id=case_two_v1.id,
        sequence_index=1,
        repositories=evaluation_repositories,
    )
    finalized_one = await snapshot_service.finalize_snapshot(
        context=context, snapshot_id=snapshot_one.id, repositories=evaluation_repositories
    )
    original_hash = finalized_one.content_hash
    original_items = await evaluation_repositories.snapshots.list_items(
        tenant_id=tenant_id, snapshot_id=snapshot_one.id
    )
    assert original_hash is not None
    assert {item.test_case_version_id for item in original_items} == {
        case_one_v1.id,
        case_two_v1.id,
    }

    # 5: revise a test case — a new version, never a rewrite.
    case_one_v2 = await dataset_service.create_test_case_version(
        context=context,
        test_case_id=case_one.id,
        content={"input": "1 + 1", "expected": "two"},
        repositories=evaluation_repositories,
    )
    assert case_one_v2.version_number == 2
    assert case_one_v2.id != case_one_v1.id

    # 6: build and finalize Snapshot 2 over the revised content.
    snapshot_two = await snapshot_service.create_draft_snapshot(
        context=context, dataset_id=dataset_id, repositories=evaluation_repositories
    )
    await snapshot_service.add_test_case_version(
        context=context,
        snapshot_id=snapshot_two.id,
        test_case_version_id=case_one_v2.id,
        sequence_index=0,
        repositories=evaluation_repositories,
    )
    await snapshot_service.add_test_case_version(
        context=context,
        snapshot_id=snapshot_two.id,
        test_case_version_id=case_two_v1.id,
        sequence_index=1,
        repositories=evaluation_repositories,
    )
    finalized_two = await snapshot_service.finalize_snapshot(
        context=context, snapshot_id=snapshot_two.id, repositories=evaluation_repositories
    )

    # 7 & 8: Snapshot 1 is byte-for-byte unchanged — same membership, same hash.
    reread_one = await evaluation_repositories.snapshots.get_snapshot(
        tenant_id=tenant_id, snapshot_id=snapshot_one.id
    )
    reread_items = await evaluation_repositories.snapshots.list_items(
        tenant_id=tenant_id, snapshot_id=snapshot_one.id
    )
    assert reread_one is not None
    assert reread_one.content_hash == original_hash
    assert {item.test_case_version_id for item in reread_items} == {
        case_one_v1.id,
        case_two_v1.id,
    }

    # 9: Snapshot 2 has a distinct identity and a distinct hash.
    assert finalized_two.id != finalized_one.id
    assert finalized_two.content_hash != finalized_one.content_hash


async def test_finalized_snapshot_rejects_further_membership_changes(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    tenant_id = await create_tenant("tenant-a")
    user_id = await create_user("engineer@example.com")
    context, dataset_id = await _setup(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    case = await dataset_service.create_test_case(
        context=context,
        dataset_id=dataset_id,
        external_key=None,
        repositories=evaluation_repositories,
    )
    version = await dataset_service.create_test_case_version(
        context=context,
        test_case_id=case.id,
        content={"input": "x"},
        repositories=evaluation_repositories,
    )
    other_case = await dataset_service.create_test_case(
        context=context,
        dataset_id=dataset_id,
        external_key="other",
        repositories=evaluation_repositories,
    )
    other_version = await dataset_service.create_test_case_version(
        context=context,
        test_case_id=other_case.id,
        content={"input": "y"},
        repositories=evaluation_repositories,
    )
    snapshot = await snapshot_service.create_draft_snapshot(
        context=context, dataset_id=dataset_id, repositories=evaluation_repositories
    )
    await snapshot_service.add_test_case_version(
        context=context,
        snapshot_id=snapshot.id,
        test_case_version_id=version.id,
        sequence_index=0,
        repositories=evaluation_repositories,
    )
    await snapshot_service.finalize_snapshot(
        context=context, snapshot_id=snapshot.id, repositories=evaluation_repositories
    )

    with pytest.raises(SnapshotNotDraftError):
        await snapshot_service.add_test_case_version(
            context=context,
            snapshot_id=snapshot.id,
            test_case_version_id=other_version.id,
            sequence_index=1,
            repositories=evaluation_repositories,
        )

    with pytest.raises(ImmutableRecordError):
        await snapshot_service.finalize_snapshot(
            context=context, snapshot_id=snapshot.id, repositories=evaluation_repositories
        )


async def test_finalized_snapshot_row_cannot_be_updated_through_direct_sql(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
    test_settings: Settings,
) -> None:
    """Even a direct SQL UPDATE against the least-privilege application
    role is blocked by the immutability trigger — the guarantee does
    not depend on every caller going through the application service."""
    tenant_id = await create_tenant("tenant-a")
    user_id = await create_user("engineer@example.com")
    context, dataset_id = await _setup(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    case = await dataset_service.create_test_case(
        context=context,
        dataset_id=dataset_id,
        external_key=None,
        repositories=evaluation_repositories,
    )
    version = await dataset_service.create_test_case_version(
        context=context,
        test_case_id=case.id,
        content={"input": "x"},
        repositories=evaluation_repositories,
    )
    snapshot = await snapshot_service.create_draft_snapshot(
        context=context, dataset_id=dataset_id, repositories=evaluation_repositories
    )
    await snapshot_service.add_test_case_version(
        context=context,
        snapshot_id=snapshot.id,
        test_case_version_id=version.id,
        sequence_index=0,
        repositories=evaluation_repositories,
    )
    await snapshot_service.finalize_snapshot(
        context=context, snapshot_id=snapshot.id, repositories=evaluation_repositories
    )

    connection = await asyncpg.connect(dsn=str(test_settings.app_database_url))
    try:
        async with connection.transaction():
            await connection.execute(
                "SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_id)
            )
            with pytest.raises(asyncpg.exceptions.RaiseError):
                await connection.execute(
                    "UPDATE dataset_snapshots SET content_hash = 'tampered' WHERE id = $1",
                    snapshot.id,
                )
    finally:
        await connection.close()
