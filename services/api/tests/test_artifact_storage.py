from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest

from evalforge_api.application import artifact_service, workspace_service
from evalforge_api.application.artifact_service import (
    ArtifactHashMismatchError,
    ArtifactNotFoundError,
    AuthorizationDeniedError,
)
from evalforge_api.domain.enums import TenantRole
from evalforge_api.domain.hashing import HASH_ALGORITHM
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]


async def _bootstrap(
    *,
    repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    slug: str,
    email: str,
) -> tuple[TenantContext, UUID]:
    tenant_id = await create_tenant(slug)
    user_id = await create_user(email)
    admin_context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.TENANT_ADMIN
    )
    workspace = await workspace_service.create_workspace(
        context=admin_context, slug="ws", name="Workspace", repositories=repositories
    )
    developer_context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.DEVELOPER
    )
    return developer_context, workspace.id


async def test_stored_artifact_bytes_round_trip_and_verify(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context, workspace_id = await _bootstrap(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="dev@example.com",
    )
    artifact = await artifact_service.create_artifact(
        context=context,
        workspace_id=workspace_id,
        media_type="application/json",
        purpose="rendered_prompt",
        repositories=evaluation_repositories,
    )

    body = b'{"prompt": "hello world"}'
    version = await artifact_service.store_artifact_version(
        context=context,
        artifact_id=artifact.id,
        body=body,
        content_type="application/json",
        derived_from_artifact_version_id=None,
        repositories=evaluation_repositories,
    )

    assert version.hash_algorithm == HASH_ALGORITHM
    assert version.byte_size == len(body)
    assert version.storage_key.startswith(f"tenants/{context.tenant_id}/artifacts/{artifact.id}/")

    retrieved = await artifact_service.retrieve_and_verify_artifact_version(
        context=context, version_id=version.id, repositories=evaluation_repositories
    )
    assert retrieved == body


async def test_object_storage_key_is_tenant_scoped(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context_a, workspace_a = await _bootstrap(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="dev-a@example.com",
    )
    context_b, workspace_b = await _bootstrap(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-b",
        email="dev-b@example.com",
    )
    artifact_a = await artifact_service.create_artifact(
        context=context_a,
        workspace_id=workspace_a,
        media_type="text/plain",
        purpose="report",
        repositories=evaluation_repositories,
    )
    artifact_b = await artifact_service.create_artifact(
        context=context_b,
        workspace_id=workspace_b,
        media_type="text/plain",
        purpose="report",
        repositories=evaluation_repositories,
    )
    version_a = await artifact_service.store_artifact_version(
        context=context_a,
        artifact_id=artifact_a.id,
        body=b"same-bytes",
        content_type="text/plain",
        derived_from_artifact_version_id=None,
        repositories=evaluation_repositories,
    )
    version_b = await artifact_service.store_artifact_version(
        context=context_b,
        artifact_id=artifact_b.id,
        body=b"same-bytes",
        content_type="text/plain",
        derived_from_artifact_version_id=None,
        repositories=evaluation_repositories,
    )

    assert version_a.storage_key != version_b.storage_key
    assert str(context_a.tenant_id) in version_a.storage_key
    assert str(context_b.tenant_id) not in version_a.storage_key


async def test_tenant_a_cannot_retrieve_tenant_bs_artifact_version(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context_a, _workspace_a = await _bootstrap(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="dev-a2@example.com",
    )
    context_b, workspace_b = await _bootstrap(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-b",
        email="dev-b2@example.com",
    )
    artifact_b = await artifact_service.create_artifact(
        context=context_b,
        workspace_id=workspace_b,
        media_type="text/plain",
        purpose="report",
        repositories=evaluation_repositories,
    )
    version_b = await artifact_service.store_artifact_version(
        context=context_b,
        artifact_id=artifact_b.id,
        body=b"tenant-b-secret",
        content_type="text/plain",
        derived_from_artifact_version_id=None,
        repositories=evaluation_repositories,
    )

    with pytest.raises(ArtifactNotFoundError):
        await artifact_service.retrieve_and_verify_artifact_version(
            context=context_a, version_id=version_b.id, repositories=evaluation_repositories
        )


async def test_hash_mismatch_is_detected_rather_than_silently_returned(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context, workspace_id = await _bootstrap(
        repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="dev-hash@example.com",
    )
    artifact = await artifact_service.create_artifact(
        context=context,
        workspace_id=workspace_id,
        media_type="text/plain",
        purpose="report",
        repositories=evaluation_repositories,
    )
    body = b"authentic-bytes"
    storage_key = f"tenants/{context.tenant_id}/artifacts/{artifact.id}/versions/1-tampered"
    await evaluation_repositories.artifact_storage.put_object(
        key=storage_key, body=body, content_type="text/plain"
    )
    # Insert metadata with a hash that does not match the stored bytes,
    # simulating corrupted or substituted object-storage content.
    version = await evaluation_repositories.artifacts.create_artifact_version(
        tenant_id=context.tenant_id,
        artifact_id=artifact.id,
        version_number=1,
        content_hash="0" * 64,
        hash_algorithm=HASH_ALGORITHM,
        byte_size=len(body),
        content_type="text/plain",
        storage_key=storage_key,
        derived_from_artifact_version_id=None,
        created_by=context.user_id,
    )

    with pytest.raises(ArtifactHashMismatchError):
        await artifact_service.retrieve_and_verify_artifact_version(
            context=context, version_id=version.id, repositories=evaluation_repositories
        )


async def test_reviewer_cannot_create_an_artifact(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    tenant_id = await create_tenant("tenant-a")
    user_id = await create_user("reviewer@example.com")
    context = build_tenant_context(tenant_id=tenant_id, user_id=user_id, role=TenantRole.REVIEWER)

    with pytest.raises(AuthorizationDeniedError):
        await artifact_service.create_artifact(
            context=context,
            workspace_id=None,
            media_type="text/plain",
            purpose="report",
            repositories=evaluation_repositories,
        )
