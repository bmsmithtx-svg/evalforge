"""Test-case lifecycle: a content change is always a new version,
archival hides without deleting, and a finalized snapshot stays
frozen no matter how the dataset around it changes.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from dataset_fixtures import (
    BuildContext,
    CreateTenant,
    CreateUser,
    add_test_case,
    bootstrap_dataset,
)
from evalforge_api.application import dataset_service, snapshot_service, test_case_service
from evalforge_api.application.dataset_errors import (
    TestCaseNotFoundError,
)
from evalforge_api.domain.evaluation_enums import TestCaseStatus
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


async def test_editing_a_test_case_produces_a_new_version_and_never_rewrites_the_old_one(
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
    first = await add_test_case(
        fixture=fixture,
        repositories=evaluation_repositories,
        content={"input": "2 + 2", "expected_output": "4"},
    )
    second = await test_case_service.create_test_case_version(
        context=fixture.context,
        test_case_id=first.test_case_id,
        content={"input": "2 + 2", "expected_output": "four"},
        repositories=evaluation_repositories,
    )

    assert second.version_number == 2
    assert second.id != first.id
    assert second.content_hash != first.content_hash
    # Same input text, so the duplicate fingerprint is unchanged.
    assert second.dedup_hash == first.dedup_hash

    history = await test_case_service.get_test_case_history(
        context=fixture.context,
        test_case_id=first.test_case_id,
        repositories=evaluation_repositories,
    )
    assert [version.version_number for version in history] == [1, 2]
    assert history[0].content_hash == first.content_hash


async def test_archiving_a_test_case_hides_it_from_active_listings_only(
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
    kept = await add_test_case(
        fixture=fixture, repositories=evaluation_repositories, content={"input": "kept"}
    )
    retired = await add_test_case(
        fixture=fixture, repositories=evaluation_repositories, content={"input": "retired"}
    )

    archived = await test_case_service.archive_test_case(
        context=fixture.context,
        test_case_id=retired.test_case_id,
        repositories=evaluation_repositories,
    )
    assert archived.status is TestCaseStatus.ARCHIVED
    assert archived.archived_at is not None

    active = await test_case_service.list_test_cases(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        status=TestCaseStatus.ACTIVE,
        repositories=evaluation_repositories,
    )
    everything = await test_case_service.list_test_cases(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        status=None,
        repositories=evaluation_repositories,
    )
    assert {case.id for case in active} == {kept.test_case_id}
    assert {case.id for case in everything} == {kept.test_case_id, retired.test_case_id}

    # The archived case's versions remain readable.
    history = await test_case_service.get_test_case_history(
        context=fixture.context,
        test_case_id=retired.test_case_id,
        repositories=evaluation_repositories,
    )
    assert len(history) == 1


async def test_archiving_an_unknown_test_case_is_not_found(
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
    with pytest.raises(TestCaseNotFoundError):
        await test_case_service.archive_test_case(
            context=fixture.context, test_case_id=uuid4(), repositories=evaluation_repositories
        )


async def test_a_finalized_snapshot_is_unaffected_by_later_dataset_mutation(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    """Regression guard: Milestone 6 made datasets and test cases
    mutable; finalized snapshots must still be frozen."""
    fixture = await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-a",
        email="a@example.com",
    )
    version = await add_test_case(
        fixture=fixture, repositories=evaluation_repositories, content={"input": "frozen"}
    )
    snapshot = await snapshot_service.create_draft_snapshot(
        context=fixture.context, dataset_id=fixture.dataset_id, repositories=evaluation_repositories
    )
    await snapshot_service.add_test_case_version(
        context=fixture.context,
        snapshot_id=snapshot.id,
        test_case_version_id=version.id,
        sequence_index=0,
        repositories=evaluation_repositories,
    )
    finalized = await snapshot_service.finalize_snapshot(
        context=fixture.context, snapshot_id=snapshot.id, repositories=evaluation_repositories
    )

    await dataset_service.update_dataset(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        name="Renamed after finalization",
        repositories=evaluation_repositories,
    )
    await test_case_service.archive_test_case(
        context=fixture.context,
        test_case_id=version.test_case_id,
        repositories=evaluation_repositories,
    )
    await dataset_service.archive_dataset(
        context=fixture.context, dataset_id=fixture.dataset_id, repositories=evaluation_repositories
    )

    reread = await snapshot_service.get_snapshot(
        context=fixture.context, snapshot_id=snapshot.id, repositories=evaluation_repositories
    )
    items = await snapshot_service.list_snapshot_items(
        context=fixture.context, snapshot_id=snapshot.id, repositories=evaluation_repositories
    )
    assert reread.content_hash == finalized.content_hash
    assert reread.item_count == 1
    assert [item.test_case_version_id for item in items] == [version.id]
