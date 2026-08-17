"""Positive behaviour of dataset cloning: content is copied, provenance
is recorded, and the source is never modified.

Negative boundaries (cross-tenant source, mismatched snapshot) live in
``test_dataset_clone_boundaries.py``.
"""

from __future__ import annotations

from dataset_fixtures import (
    BuildContext,
    CreateTenant,
    CreateUser,
    add_test_case,
    bootstrap_dataset,
)
from evalforge_api.application import dataset_clone_service, snapshot_service, test_case_service
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


async def test_cloning_current_state_copies_content_and_records_provenance(
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
        content={"input": "question one"},
        external_key="case-1",
    )
    second = await add_test_case(
        fixture=fixture,
        repositories=evaluation_repositories,
        content={"input": "question two"},
        external_key="case-2",
    )

    clone = await dataset_clone_service.clone_dataset(
        context=fixture.context,
        source_dataset_id=fixture.dataset_id,
        source_snapshot_id=None,
        new_name="Cloned dataset",
        repositories=evaluation_repositories,
    )

    assert clone.id != fixture.dataset_id
    assert clone.name == "Cloned dataset"
    assert clone.source == "cloned"
    assert clone.cloned_from_dataset_id == fixture.dataset_id
    assert clone.cloned_from_snapshot_id is None

    cloned_versions = await evaluation_repositories.datasets.list_latest_versions_for_dataset(
        tenant_id=fixture.tenant_id, dataset_id=clone.id
    )
    assert len(cloned_versions) == 2
    assert {version.content_hash for version in cloned_versions} == {
        first.content_hash,
        second.content_hash,
    }
    # New logical resources: fresh IDs, version history restarted at 1.
    assert all(version.version_number == 1 for version in cloned_versions)
    assert {version.test_case_id for version in cloned_versions}.isdisjoint(
        {first.test_case_id, second.test_case_id}
    )

    cloned_cases = await evaluation_repositories.datasets.list_test_cases(
        tenant_id=fixture.tenant_id, dataset_id=clone.id, status=None
    )
    assert {case.source for case in cloned_cases} == {"cloned"}
    assert {case.source_test_case_id for case in cloned_cases} == {
        first.test_case_id,
        second.test_case_id,
    }
    assert {case.external_key for case in cloned_cases} == {"case-1", "case-2"}


async def test_cloning_never_mutates_the_source_dataset(
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
    original = await add_test_case(
        fixture=fixture, repositories=evaluation_repositories, content={"input": "source content"}
    )
    before = await evaluation_repositories.datasets.get_dataset(
        tenant_id=fixture.tenant_id, dataset_id=fixture.dataset_id
    )

    clone = await dataset_clone_service.clone_dataset(
        context=fixture.context,
        source_dataset_id=fixture.dataset_id,
        source_snapshot_id=None,
        new_name="Clone",
        repositories=evaluation_repositories,
    )
    # Diverge the clone.
    cloned_cases = await evaluation_repositories.datasets.list_test_cases(
        tenant_id=fixture.tenant_id, dataset_id=clone.id, status=None
    )
    await test_case_service.create_test_case_version(
        context=fixture.context,
        test_case_id=cloned_cases[0].id,
        content={"input": "diverged content"},
        repositories=evaluation_repositories,
    )

    after = await evaluation_repositories.datasets.get_dataset(
        tenant_id=fixture.tenant_id, dataset_id=fixture.dataset_id
    )
    source_cases = await evaluation_repositories.datasets.list_test_cases(
        tenant_id=fixture.tenant_id, dataset_id=fixture.dataset_id, status=None
    )
    source_versions = await evaluation_repositories.datasets.list_test_case_versions(
        tenant_id=fixture.tenant_id, test_case_id=original.test_case_id
    )
    assert before == after
    assert len(source_cases) == 1
    assert len(source_versions) == 1
    assert source_versions[0].content_hash == original.content_hash


async def test_cloning_from_a_snapshot_copies_the_frozen_content_not_the_current_content(
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
    frozen = await add_test_case(
        fixture=fixture, repositories=evaluation_repositories, content={"input": "frozen content"}
    )
    snapshot = await snapshot_service.create_draft_snapshot(
        context=fixture.context, dataset_id=fixture.dataset_id, repositories=evaluation_repositories
    )
    await snapshot_service.add_test_case_version(
        context=fixture.context,
        snapshot_id=snapshot.id,
        test_case_version_id=frozen.id,
        sequence_index=0,
        repositories=evaluation_repositories,
    )
    await snapshot_service.finalize_snapshot(
        context=fixture.context, snapshot_id=snapshot.id, repositories=evaluation_repositories
    )
    # The dataset moves on after the snapshot was frozen.
    await test_case_service.create_test_case_version(
        context=fixture.context,
        test_case_id=frozen.test_case_id,
        content={"input": "content after the snapshot"},
        repositories=evaluation_repositories,
    )

    clone = await dataset_clone_service.clone_dataset(
        context=fixture.context,
        source_dataset_id=fixture.dataset_id,
        source_snapshot_id=snapshot.id,
        new_name="From snapshot",
        repositories=evaluation_repositories,
    )
    assert clone.cloned_from_snapshot_id == snapshot.id

    cloned_versions = await evaluation_repositories.datasets.list_latest_versions_for_dataset(
        tenant_id=fixture.tenant_id, dataset_id=clone.id
    )
    assert len(cloned_versions) == 1
    assert cloned_versions[0].content["input"] == "frozen content"
    assert cloned_versions[0].content_hash == frozen.content_hash


async def test_cloning_an_empty_dataset_produces_an_empty_clone(
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
    clone = await dataset_clone_service.clone_dataset(
        context=fixture.context,
        source_dataset_id=fixture.dataset_id,
        source_snapshot_id=None,
        new_name="Empty clone",
        repositories=evaluation_repositories,
    )
    cases = await evaluation_repositories.datasets.list_test_cases(
        tenant_id=fixture.tenant_id, dataset_id=clone.id, status=None
    )
    assert cases == ()
