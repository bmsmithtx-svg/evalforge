from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

import asyncpg
import pytest

from evalforge_api.application import lineage_service, versioned_resource_service, workspace_service
from evalforge_api.application.versioned_resource_service import AuthorizationDeniedError
from evalforge_api.domain.enums import TenantRole
from evalforge_api.domain.evaluation_enums import ResourceKind
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.domain.versioning import LineageViolationError
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]


async def _setup_workspace(
    *,
    repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    tenant_id: UUID,
    user_id: UUID,
) -> UUID:
    admin_context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.TENANT_ADMIN
    )
    workspace = await workspace_service.create_workspace(
        context=admin_context, slug="ws-a", name="Workspace A", repositories=repositories
    )
    return workspace.id


async def test_creating_versions_always_increments_and_never_rewrites(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    tenant_id = await create_tenant("tenant-a")
    user_id = await create_user("engineer@example.com")
    workspace_id = await _setup_workspace(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.EVALUATION_ENGINEER
    )

    resource = await versioned_resource_service.create_resource(
        context=context,
        workspace_id=workspace_id,
        kind=ResourceKind.EVALUATOR_DEFINITION,
        name="exact-match",
        repositories=evaluation_repositories,
    )
    v1 = await versioned_resource_service.create_version(
        context=context,
        resource_id=resource.id,
        content={"threshold": 0.8},
        derived_from_version_id=None,
        repositories=evaluation_repositories,
    )
    v2 = await versioned_resource_service.create_version(
        context=context,
        resource_id=resource.id,
        content={"threshold": 0.9},
        derived_from_version_id=v1.id,
        repositories=evaluation_repositories,
    )

    assert v1.version_number == 1
    assert v2.version_number == 2
    assert v1.content_hash != v2.content_hash

    reread_v1 = await evaluation_repositories.versioned_resources.get_version(
        tenant_id=tenant_id, version_id=v1.id
    )
    assert reread_v1 is not None
    assert reread_v1.content == {"threshold": 0.8}


async def test_derived_from_across_resources_is_rejected(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    tenant_id = await create_tenant("tenant-a")
    user_id = await create_user("engineer2@example.com")
    workspace_id = await _setup_workspace(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.EVALUATION_ENGINEER
    )

    resource_one = await versioned_resource_service.create_resource(
        context=context,
        workspace_id=workspace_id,
        kind=ResourceKind.PROMPT_CONFIG,
        name="prompt-one",
        repositories=evaluation_repositories,
    )
    resource_two = await versioned_resource_service.create_resource(
        context=context,
        workspace_id=workspace_id,
        kind=ResourceKind.PROMPT_CONFIG,
        name="prompt-two",
        repositories=evaluation_repositories,
    )
    version_one = await versioned_resource_service.create_version(
        context=context,
        resource_id=resource_one.id,
        content={"text": "a"},
        derived_from_version_id=None,
        repositories=evaluation_repositories,
    )

    with pytest.raises(LineageViolationError):
        await versioned_resource_service.create_version(
            context=context,
            resource_id=resource_two.id,
            content={"text": "b"},
            derived_from_version_id=version_one.id,
            repositories=evaluation_repositories,
        )


async def test_database_trigger_rejects_cross_resource_lineage_even_bypassing_the_domain_check(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    """The application service already rejects this
    (``test_derived_from_across_resources_is_rejected``); this proves
    the database trigger is an independent second layer by calling
    the repository directly, bypassing
    ``evalforge_api.domain.versioning.validate_lineage_within_resource``."""
    tenant_id = await create_tenant("tenant-a")
    user_id = await create_user("engineer3@example.com")
    workspace_id = await _setup_workspace(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.EVALUATION_ENGINEER
    )
    resource_one = await versioned_resource_service.create_resource(
        context=context,
        workspace_id=workspace_id,
        kind=ResourceKind.PROMPT_CONFIG,
        name="prompt-one",
        repositories=evaluation_repositories,
    )
    resource_two = await versioned_resource_service.create_resource(
        context=context,
        workspace_id=workspace_id,
        kind=ResourceKind.PROMPT_CONFIG,
        name="prompt-two",
        repositories=evaluation_repositories,
    )
    version_one = await versioned_resource_service.create_version(
        context=context,
        resource_id=resource_one.id,
        content={"text": "a"},
        derived_from_version_id=None,
        repositories=evaluation_repositories,
    )

    with pytest.raises(asyncpg.exceptions.RaiseError):
        await evaluation_repositories.versioned_resources.create_version(
            tenant_id=tenant_id,
            resource_id=resource_two.id,
            version_number=1,
            content={"text": "b"},
            content_hash="deadbeef",
            hash_algorithm="sha256",
            canonicalization_version="json-canonical-v1",
            derived_from_version_id=version_one.id,
            created_by=user_id,
        )


async def test_read_only_observer_cannot_create_versioned_resources(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    tenant_id = await create_tenant("tenant-a")
    user_id = await create_user("observer@example.com")
    workspace_id = await _setup_workspace(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.READ_ONLY_OBSERVER
    )

    with pytest.raises(AuthorizationDeniedError):
        await versioned_resource_service.create_resource(
            context=context,
            workspace_id=workspace_id,
            kind=ResourceKind.MODEL_CONFIG,
            name="denied",
            repositories=evaluation_repositories,
        )


async def test_lineage_ancestry_follows_the_derivation_chain(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    tenant_id = await create_tenant("tenant-a")
    user_id = await create_user("lineage@example.com")
    workspace_id = await _setup_workspace(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.EVALUATION_ENGINEER
    )
    resource = await versioned_resource_service.create_resource(
        context=context,
        workspace_id=workspace_id,
        kind=ResourceKind.PRICING_ASSUMPTION,
        name="pricing",
        repositories=evaluation_repositories,
    )
    v1 = await versioned_resource_service.create_version(
        context=context,
        resource_id=resource.id,
        content={"rate": 1},
        derived_from_version_id=None,
        repositories=evaluation_repositories,
    )
    v2 = await versioned_resource_service.create_version(
        context=context,
        resource_id=resource.id,
        content={"rate": 2},
        derived_from_version_id=v1.id,
        repositories=evaluation_repositories,
    )
    v3 = await versioned_resource_service.create_version(
        context=context,
        resource_id=resource.id,
        content={"rate": 3},
        derived_from_version_id=v2.id,
        repositories=evaluation_repositories,
    )

    ancestry = await lineage_service.resource_version_ancestry(
        context=context, version_id=v3.id, repositories=evaluation_repositories
    )

    assert [version.id for version in ancestry] == [v3.id, v2.id, v1.id]
