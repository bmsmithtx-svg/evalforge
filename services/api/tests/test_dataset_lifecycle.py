"""Dataset-container lifecycle: creation with metadata, partial
update, archival, and filtered listing.

Test-case authoring and archival live in
``test_test_case_lifecycle.py``.
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
from evalforge_api.application import dataset_service
from evalforge_api.application.dataset_errors import (
    DatasetNotFoundError,
)
from evalforge_api.domain.evaluation_enums import DatasetStatus
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


async def test_dataset_is_created_with_metadata_and_manual_provenance(
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
    dataset = await dataset_service.create_dataset(
        context=fixture.context,
        workspace_id=fixture.workspace_id,
        name="Support QA",
        description="Tier-1 support answers",
        tags=("support", "regression"),
        metadata={"owner": "quality"},
        repositories=evaluation_repositories,
    )
    assert dataset.name == "Support QA"
    assert dataset.description == "Tier-1 support answers"
    assert dataset.tags == ("support", "regression")
    assert dataset.metadata == {"owner": "quality"}
    assert dataset.status is DatasetStatus.ACTIVE
    assert dataset.source == "manual"
    assert dataset.cloned_from_dataset_id is None
    assert dataset.archived_at is None
    assert dataset.updated_by is None


async def test_updating_a_dataset_changes_only_the_supplied_fields(
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
    await dataset_service.update_dataset(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        description="First description",
        tags=("alpha",),
        repositories=evaluation_repositories,
    )
    updated = await dataset_service.update_dataset(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        name="Renamed",
        repositories=evaluation_repositories,
    )
    assert updated.name == "Renamed"
    assert updated.description == "First description"
    assert updated.tags == ("alpha",)
    assert updated.updated_by == fixture.user_id


async def test_updating_a_nonexistent_dataset_is_not_found(
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
    with pytest.raises(DatasetNotFoundError):
        await dataset_service.update_dataset(
            context=fixture.context,
            dataset_id=uuid4(),
            name="Nope",
            repositories=evaluation_repositories,
        )


async def test_archiving_a_dataset_sets_status_and_timestamp_without_deleting_content(
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
        fixture=fixture, repositories=evaluation_repositories, content={"input": "keep me"}
    )

    archived = await dataset_service.archive_dataset(
        context=fixture.context, dataset_id=fixture.dataset_id, repositories=evaluation_repositories
    )
    assert archived.status is DatasetStatus.ARCHIVED
    assert archived.archived_at is not None

    # Versioned content survives archival untouched.
    reread = await evaluation_repositories.datasets.get_test_case_version(
        tenant_id=fixture.tenant_id, version_id=version.id
    )
    assert reread is not None
    assert reread.content_hash == version.content_hash


async def test_listing_datasets_can_filter_by_status_and_workspace(
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
    second = await dataset_service.create_dataset(
        context=fixture.context,
        workspace_id=fixture.workspace_id,
        name="Second",
        repositories=evaluation_repositories,
    )
    await dataset_service.archive_dataset(
        context=fixture.context, dataset_id=second.id, repositories=evaluation_repositories
    )

    everything = await dataset_service.list_datasets(
        context=fixture.context, repositories=evaluation_repositories
    )
    active_only = await dataset_service.list_datasets(
        context=fixture.context,
        status=DatasetStatus.ACTIVE,
        repositories=evaluation_repositories,
    )
    other_workspace = await dataset_service.list_datasets(
        context=fixture.context, workspace_id=uuid4(), repositories=evaluation_repositories
    )

    assert {dataset.id for dataset in everything} == {fixture.dataset_id, second.id}
    assert {dataset.id for dataset in active_only} == {fixture.dataset_id}
    assert other_workspace == ()
