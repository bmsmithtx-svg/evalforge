"""Shared setup helpers for the Milestone 6 dataset-management tests.

Not a pytest plugin and not a dumping ground: this is the one
dataset-management bootstrap sequence (tenant -> user -> workspace ->
dataset) that every dataset test needs, kept in one place so each test
module can stay focused on the behavior it is actually asserting.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from evalforge_api.application import dataset_service, test_case_service, workspace_service
from evalforge_api.domain.enums import TenantRole
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.datasets import TestCaseVersionRecord
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]


@dataclass(frozen=True, slots=True)
class DatasetFixture:
    tenant_id: UUID
    user_id: UUID
    workspace_id: UUID
    dataset_id: UUID
    context: TenantContext


async def bootstrap_dataset(
    *,
    repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
    slug: str,
    email: str,
    dataset_name: str = "Dataset",
) -> DatasetFixture:
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
    dataset = await dataset_service.create_dataset(
        context=engineer_context,
        workspace_id=workspace.id,
        name=dataset_name,
        repositories=repositories,
    )
    return DatasetFixture(
        tenant_id=tenant_id,
        user_id=user_id,
        workspace_id=workspace.id,
        dataset_id=dataset.id,
        context=engineer_context,
    )


async def bootstrap_two_tenants(
    *,
    repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> tuple[DatasetFixture, DatasetFixture]:
    """Two fully isolated tenants, each with its own dataset — the
    standing arrangement for every cross-tenant negative test."""
    tenant_a = await bootstrap_dataset(
        repositories=repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-a",
        email="a@example.com",
    )
    tenant_b = await bootstrap_dataset(
        repositories=repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-b",
        email="b@example.com",
        dataset_name="Tenant B private dataset",
    )
    return tenant_a, tenant_b


async def add_test_case(
    *,
    fixture: DatasetFixture,
    repositories: EvaluationRepositories,
    content: dict[str, Any],
    external_key: str | None = None,
    dataset_id: UUID | None = None,
) -> TestCaseVersionRecord:
    """Create a test case and its first content version."""
    test_case = await test_case_service.create_test_case(
        context=fixture.context,
        dataset_id=dataset_id or fixture.dataset_id,
        external_key=external_key,
        repositories=repositories,
    )
    return await test_case_service.create_test_case_version(
        context=fixture.context,
        test_case_id=test_case.id,
        content=content,
        repositories=repositories,
    )
