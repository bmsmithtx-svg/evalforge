from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from dataset_fixtures import (
    BuildContext,
    CreateTenant,
    CreateUser,
    DatasetFixture,
    add_test_case,
    bootstrap_dataset,
)
from evalforge_api.application import snapshot_comparison_service, snapshot_service
from evalforge_api.application.dataset_errors import SnapshotNotFoundError
from evalforge_api.domain.enums import TenantRole
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


async def _finalized_snapshot(
    *,
    fixture: DatasetFixture,
    repositories: EvaluationRepositories,
    version_ids: tuple[UUID, ...],
) -> UUID:
    snapshot = await snapshot_service.create_draft_snapshot(
        context=fixture.context, dataset_id=fixture.dataset_id, repositories=repositories
    )
    for index, version_id in enumerate(version_ids):
        await snapshot_service.add_test_case_version(
            context=fixture.context,
            snapshot_id=snapshot.id,
            test_case_version_id=version_id,
            sequence_index=index,
            repositories=repositories,
        )
    await snapshot_service.finalize_snapshot(
        context=fixture.context, snapshot_id=snapshot.id, repositories=repositories
    )
    return snapshot.id


async def test_comparison_reports_added_removed_changed_and_unchanged(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    from evalforge_api.application import test_case_service

    fixture = await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-a",
        email="a@example.com",
    )
    kept = await add_test_case(
        fixture=fixture, repositories=evaluation_repositories, content={"input": "kept"}
    )
    revised = await add_test_case(
        fixture=fixture, repositories=evaluation_repositories, content={"input": "revised v1"}
    )
    dropped = await add_test_case(
        fixture=fixture, repositories=evaluation_repositories, content={"input": "dropped"}
    )

    left_id = await _finalized_snapshot(
        fixture=fixture,
        repositories=evaluation_repositories,
        version_ids=(kept.id, revised.id, dropped.id),
    )

    revised_v2 = await test_case_service.create_test_case_version(
        context=fixture.context,
        test_case_id=revised.test_case_id,
        content={"input": "revised v2"},
        repositories=evaluation_repositories,
    )
    introduced = await add_test_case(
        fixture=fixture, repositories=evaluation_repositories, content={"input": "introduced"}
    )
    right_id = await _finalized_snapshot(
        fixture=fixture,
        repositories=evaluation_repositories,
        version_ids=(kept.id, revised_v2.id, introduced.id),
    )

    result = await snapshot_comparison_service.compare_snapshots(
        context=fixture.context,
        left_snapshot_id=left_id,
        right_snapshot_id=right_id,
        repositories=evaluation_repositories,
    )
    assert result.added == (introduced.test_case_id,)
    assert result.removed == (dropped.test_case_id,)
    assert result.changed == ((revised.test_case_id, 1, 2),)
    assert result.unchanged == (kept.test_case_id,)


async def test_comparing_a_snapshot_with_itself_reports_no_differences(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    fixture = await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-a",
        email="a@example.com",
    )
    version = await add_test_case(
        fixture=fixture, repositories=evaluation_repositories, content={"input": "only"}
    )
    snapshot_id = await _finalized_snapshot(
        fixture=fixture, repositories=evaluation_repositories, version_ids=(version.id,)
    )
    result = await snapshot_comparison_service.compare_snapshots(
        context=fixture.context,
        left_snapshot_id=snapshot_id,
        right_snapshot_id=snapshot_id,
        repositories=evaluation_repositories,
    )
    assert result.added == ()
    assert result.removed == ()
    assert result.changed == ()
    assert result.unchanged == (version.test_case_id,)


async def test_an_unknown_snapshot_id_yields_an_undifferentiated_not_found(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    fixture = await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-a",
        email="a@example.com",
    )
    version = await add_test_case(
        fixture=fixture, repositories=evaluation_repositories, content={"input": "only"}
    )
    real = await _finalized_snapshot(
        fixture=fixture, repositories=evaluation_repositories, version_ids=(version.id,)
    )
    missing = uuid4()

    with pytest.raises(SnapshotNotFoundError) as left_missing:
        await snapshot_comparison_service.compare_snapshots(
            context=fixture.context,
            left_snapshot_id=missing,
            right_snapshot_id=real,
            repositories=evaluation_repositories,
        )
    with pytest.raises(SnapshotNotFoundError) as right_missing:
        await snapshot_comparison_service.compare_snapshots(
            context=fixture.context,
            left_snapshot_id=real,
            right_snapshot_id=missing,
            repositories=evaluation_repositories,
        )
    # Identical messages: which side failed is never disclosed.
    assert str(left_missing.value) == str(right_missing.value)
    assert str(missing) not in str(left_missing.value)


async def test_another_tenants_snapshot_is_indistinguishable_from_a_missing_one(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    tenant_a = await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-a",
        email="a@example.com",
    )
    tenant_b = await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-b",
        email="b@example.com",
    )
    version_a = await add_test_case(
        fixture=tenant_a, repositories=evaluation_repositories, content={"input": "a"}
    )
    version_b = await add_test_case(
        fixture=tenant_b, repositories=evaluation_repositories, content={"input": "b"}
    )
    snapshot_a = await _finalized_snapshot(
        fixture=tenant_a, repositories=evaluation_repositories, version_ids=(version_a.id,)
    )
    snapshot_b = await _finalized_snapshot(
        fixture=tenant_b, repositories=evaluation_repositories, version_ids=(version_b.id,)
    )

    with pytest.raises(SnapshotNotFoundError):
        await snapshot_comparison_service.compare_snapshots(
            context=tenant_a.context,
            left_snapshot_id=snapshot_a,
            right_snapshot_id=snapshot_b,
            repositories=evaluation_repositories,
        )


async def test_every_role_including_read_only_may_compare_snapshots(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    fixture = await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-a",
        email="a@example.com",
    )
    version = await add_test_case(
        fixture=fixture, repositories=evaluation_repositories, content={"input": "only"}
    )
    snapshot_id = await _finalized_snapshot(
        fixture=fixture, repositories=evaluation_repositories, version_ids=(version.id,)
    )
    observer = build_tenant_context(
        tenant_id=fixture.tenant_id,
        user_id=fixture.user_id,
        role=TenantRole.READ_ONLY_OBSERVER,
    )
    result = await snapshot_comparison_service.compare_snapshots(
        context=observer,
        left_snapshot_id=snapshot_id,
        right_snapshot_id=snapshot_id,
        repositories=evaluation_repositories,
    )
    assert result.unchanged == (version.test_case_id,)
