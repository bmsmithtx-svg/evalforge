"""Negative boundaries of dataset cloning.

The positive behaviour (content copied, provenance recorded, source
untouched) lives in ``test_dataset_clone.py``.
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
    bootstrap_two_tenants,
)
from evalforge_api.application import dataset_clone_service, dataset_service, snapshot_service
from evalforge_api.application.dataset_errors import DatasetNotFoundError, SnapshotNotFoundError
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


async def test_cloning_another_tenants_dataset_is_not_found(
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
            new_name="Stolen",
            repositories=evaluation_repositories,
        )
    # Identical outcome for a random UUID: no existence disclosure.
    with pytest.raises(DatasetNotFoundError):
        await dataset_clone_service.clone_dataset(
            context=tenant_a.context,
            source_dataset_id=uuid4(),
            source_snapshot_id=None,
            new_name="Stolen",
            repositories=evaluation_repositories,
        )


async def test_cloning_with_a_snapshot_from_another_dataset_is_not_found(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    """A snapshot the caller owns, but belonging to a different
    dataset, is still not a valid clone source."""
    fixture = await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-a",
        email="a@example.com",
    )
    other = await dataset_service.create_dataset(
        context=fixture.context,
        workspace_id=fixture.workspace_id,
        name="Other",
        repositories=evaluation_repositories,
    )
    other_snapshot = await snapshot_service.create_draft_snapshot(
        context=fixture.context, dataset_id=other.id, repositories=evaluation_repositories
    )

    with pytest.raises(SnapshotNotFoundError):
        await dataset_clone_service.clone_dataset(
            context=fixture.context,
            source_dataset_id=fixture.dataset_id,
            source_snapshot_id=other_snapshot.id,
            new_name="Mismatched",
            repositories=evaluation_repositories,
        )
