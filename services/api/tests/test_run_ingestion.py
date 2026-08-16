from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

import pytest

from evalforge_api.application import run_service, versioned_resource_service, workspace_service
from evalforge_api.application.ingestion_validation import (
    ReferencedResourceKindMismatchError,
    ReferencedResourceNotFoundError,
    ReferencedWorkspaceNotFoundError,
)
from evalforge_api.application.run_service import AuthorizationDeniedError
from evalforge_api.domain.enums import TenantRole
from evalforge_api.domain.evaluation_enums import ResourceKind
from evalforge_api.domain.hashing import hash_canonical_content
from evalforge_api.domain.ingestion_enums import RunStatus
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]


async def bootstrap_run_tenant(
    *,
    evaluation_repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    slug: str,
    email: str,
    role: TenantRole = TenantRole.DEVELOPER,
) -> tuple[TenantContext, UUID]:
    tenant_id = await create_tenant(slug)
    user_id = await create_user(email)
    admin_context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.TENANT_ADMIN
    )
    workspace = await workspace_service.create_workspace(
        context=admin_context, slug="ws", name="Workspace", repositories=evaluation_repositories
    )
    context = build_tenant_context(tenant_id=tenant_id, user_id=user_id, role=role)
    return context, workspace.id


async def create_run(
    *,
    context: TenantContext,
    workspace_id: UUID,
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    idempotency_key: str = "key-1",
    request_fingerprint: str | None = None,
    model_version_id: UUID | None = None,
) -> tuple[object, bool]:
    return await run_service.create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_target_id=None,
        model_version_id=model_version_id,
        prompt_version_id=None,
        retrieval_config_version_id=None,
        workflow_version_id=None,
        pricing_version_id=None,
        tool_definition_version_ids=(),
        source="pytest-sdk",
        correlation_id=None,
        started_at=datetime.now(UTC),
        metadata={"note": "test"},
        schema_version="run-v1",
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint or hash_canonical_content({"key": idempotency_key}),
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )


async def test_developer_can_ingest_a_run(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context, workspace_id = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="dev@example.com",
    )
    run, created = await create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    assert created is True
    assert run.status == RunStatus.RUNNING
    assert run.workspace_id == workspace_id


async def test_reviewer_cannot_ingest_a_run(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context, workspace_id = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="reviewer@example.com",
        role=TenantRole.REVIEWER,
    )
    with pytest.raises(AuthorizationDeniedError):
        await create_run(
            context=context,
            workspace_id=workspace_id,
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
        )


async def test_cross_tenant_workspace_reference_is_rejected(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context_a, _workspace_a = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="a@example.com",
    )
    _context_b, workspace_b = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-b",
        email="b@example.com",
    )
    with pytest.raises(ReferencedWorkspaceNotFoundError):
        await create_run(
            context=context_a,
            workspace_id=workspace_b,
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
        )


async def test_cross_tenant_model_version_reference_is_rejected(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context_a, workspace_a = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="a2@example.com",
    )
    context_b, workspace_b = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-b",
        email="b2@example.com",
    )
    resource_b = await versioned_resource_service.create_resource(
        context=context_b,
        workspace_id=workspace_b,
        kind=ResourceKind.MODEL_CONFIG,
        name="tenant-b-model",
        repositories=evaluation_repositories,
    )
    version_b = await versioned_resource_service.create_version(
        context=context_b,
        resource_id=resource_b.id,
        content={"provider": "acme"},
        derived_from_version_id=None,
        repositories=evaluation_repositories,
    )
    with pytest.raises(ReferencedResourceNotFoundError):
        await create_run(
            context=context_a,
            workspace_id=workspace_a,
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
            model_version_id=version_b.id,
        )


async def test_wrong_resource_kind_reference_is_rejected(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context, workspace_id = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="kindcheck@example.com",
    )
    prompt_resource = await versioned_resource_service.create_resource(
        context=context,
        workspace_id=workspace_id,
        kind=ResourceKind.PROMPT_CONFIG,
        name="a-prompt",
        repositories=evaluation_repositories,
    )
    prompt_version = await versioned_resource_service.create_version(
        context=context,
        resource_id=prompt_resource.id,
        content={"template": "hi"},
        derived_from_version_id=None,
        repositories=evaluation_repositories,
    )
    with pytest.raises(ReferencedResourceKindMismatchError):
        await create_run(
            context=context,
            workspace_id=workspace_id,
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
            model_version_id=prompt_version.id,
        )
