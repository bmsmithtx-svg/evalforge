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
from evalforge_api.application import dataset_sampling_service, snapshot_service
from evalforge_api.application.dataset_errors import (
    SnapshotNotFinalizedError,
    SnapshotNotFoundError,
)
from evalforge_api.domain.sampling import InvalidSamplingRequestError
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


async def _populated_draft(
    *, fixture: DatasetFixture, repositories: EvaluationRepositories, size: int
) -> tuple[UUID, tuple[UUID, ...]]:
    version_ids: list[UUID] = []
    for index in range(size):
        version = await add_test_case(
            fixture=fixture,
            repositories=repositories,
            content={"input": f"question {index}"},
            external_key=f"case-{index}",
        )
        version_ids.append(version.id)
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
    return snapshot.id, tuple(version_ids)


async def test_sampling_a_finalized_snapshot_is_reproducible(
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
    snapshot_id, version_ids = await _populated_draft(
        fixture=fixture, repositories=evaluation_repositories, size=10
    )
    await snapshot_service.finalize_snapshot(
        context=fixture.context, snapshot_id=snapshot_id, repositories=evaluation_repositories
    )

    first = await dataset_sampling_service.sample_snapshot(
        context=fixture.context,
        snapshot_id=snapshot_id,
        sample_size=4,
        seed="release-2026-08",
        repositories=evaluation_repositories,
    )
    second = await dataset_sampling_service.sample_snapshot(
        context=fixture.context,
        snapshot_id=snapshot_id,
        sample_size=4,
        seed="release-2026-08",
        repositories=evaluation_repositories,
    )
    other_seed = await dataset_sampling_service.sample_snapshot(
        context=fixture.context,
        snapshot_id=snapshot_id,
        sample_size=4,
        seed="a-different-seed",
        repositories=evaluation_repositories,
    )

    assert first == second
    assert first != other_seed
    assert len(first) == 4
    assert set(first) <= set(version_ids)


async def test_splitting_a_finalized_snapshot_partitions_every_item_once(
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
    snapshot_id, version_ids = await _populated_draft(
        fixture=fixture, repositories=evaluation_repositories, size=12
    )
    await snapshot_service.finalize_snapshot(
        context=fixture.context, snapshot_id=snapshot_id, repositories=evaluation_repositories
    )

    buckets = await dataset_sampling_service.split_snapshot(
        context=fixture.context,
        snapshot_id=snapshot_id,
        ratios={"train": 0.75, "holdout": 0.25},
        seed="split-seed",
        repositories=evaluation_repositories,
    )
    assigned = [item for members in buckets.values() for item in members]
    assert set(buckets) == {"train", "holdout"}
    assert sorted(assigned, key=str) == sorted(version_ids, key=str)
    assert len(assigned) == len(set(assigned))

    repeated = await dataset_sampling_service.split_snapshot(
        context=fixture.context,
        snapshot_id=snapshot_id,
        ratios={"train": 0.75, "holdout": 0.25},
        seed="split-seed",
        repositories=evaluation_repositories,
    )
    assert repeated == buckets


async def test_sampling_a_draft_snapshot_is_rejected(
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
    snapshot_id, _ = await _populated_draft(
        fixture=fixture, repositories=evaluation_repositories, size=3
    )
    with pytest.raises(SnapshotNotFinalizedError):
        await dataset_sampling_service.sample_snapshot(
            context=fixture.context,
            snapshot_id=snapshot_id,
            sample_size=1,
            seed="seed",
            repositories=evaluation_repositories,
        )
    with pytest.raises(SnapshotNotFinalizedError):
        await dataset_sampling_service.split_snapshot(
            context=fixture.context,
            snapshot_id=snapshot_id,
            ratios={"a": 1.0},
            seed="seed",
            repositories=evaluation_repositories,
        )


async def test_sampling_more_items_than_the_snapshot_holds_is_rejected(
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
    snapshot_id, _ = await _populated_draft(
        fixture=fixture, repositories=evaluation_repositories, size=2
    )
    await snapshot_service.finalize_snapshot(
        context=fixture.context, snapshot_id=snapshot_id, repositories=evaluation_repositories
    )
    with pytest.raises(InvalidSamplingRequestError):
        await dataset_sampling_service.sample_snapshot(
            context=fixture.context,
            snapshot_id=snapshot_id,
            sample_size=5,
            seed="seed",
            repositories=evaluation_repositories,
        )


async def test_sampling_another_tenants_snapshot_is_not_found(
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
    snapshot_b, _ = await _populated_draft(
        fixture=tenant_b, repositories=evaluation_repositories, size=2
    )
    await snapshot_service.finalize_snapshot(
        context=tenant_b.context, snapshot_id=snapshot_b, repositories=evaluation_repositories
    )

    with pytest.raises(SnapshotNotFoundError):
        await dataset_sampling_service.sample_snapshot(
            context=tenant_a.context,
            snapshot_id=snapshot_b,
            sample_size=1,
            seed="seed",
            repositories=evaluation_repositories,
        )
    with pytest.raises(SnapshotNotFoundError):
        await dataset_sampling_service.sample_snapshot(
            context=tenant_a.context,
            snapshot_id=uuid4(),
            sample_size=1,
            seed="seed",
            repositories=evaluation_repositories,
        )
