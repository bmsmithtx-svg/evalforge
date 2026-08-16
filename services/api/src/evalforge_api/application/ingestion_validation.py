"""Shared cross-tenant-safe reference validation for Milestone 5
ingestion services.

Every optional lineage or artifact reference an ingestion request
supplies must be independently re-verified as belonging to the
requesting tenant — a caller-supplied UUID is never proof of ownership
(docs/TENANCY_AND_AUTHORIZATION.md). Repository lookups are already
tenant-scoped (a cross-tenant ID returns ``None``, never another
tenant's row), so these helpers only translate "not found" or "wrong
kind" into a typed domain error the calling service can map to a 4xx
response.
"""

from __future__ import annotations

from uuid import UUID

from evalforge_api.domain.evaluation_enums import ResourceKind
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


class ReferencedResourceNotFoundError(Exception):
    pass


class ReferencedResourceKindMismatchError(Exception):
    pass


class ReferencedArtifactNotFoundError(Exception):
    pass


class ReferencedWorkspaceNotFoundError(Exception):
    pass


class ReferencedEvaluationTargetNotFoundError(Exception):
    pass


async def validate_resource_version(
    *,
    repositories: EvaluationRepositories,
    tenant_id: UUID,
    version_id: UUID,
    expected_kind: ResourceKind,
) -> None:
    version = await repositories.versioned_resources.get_version(
        tenant_id=tenant_id, version_id=version_id
    )
    if version is None:
        raise ReferencedResourceNotFoundError(str(version_id))
    resource = await repositories.versioned_resources.get_resource(
        tenant_id=tenant_id, resource_id=version.resource_id
    )
    if resource is None or resource.kind != expected_kind:
        raise ReferencedResourceKindMismatchError(
            f"{version_id} is not a {expected_kind.value} version"
        )


async def validate_artifact_version(
    *, repositories: EvaluationRepositories, tenant_id: UUID, version_id: UUID
) -> None:
    version = await repositories.artifacts.get_artifact_version(
        tenant_id=tenant_id, version_id=version_id
    )
    if version is None:
        raise ReferencedArtifactNotFoundError(str(version_id))


async def validate_workspace(
    *, repositories: EvaluationRepositories, tenant_id: UUID, workspace_id: UUID
) -> None:
    workspace = await repositories.workspaces.get_by_id(
        tenant_id=tenant_id, workspace_id=workspace_id
    )
    if workspace is None:
        raise ReferencedWorkspaceNotFoundError(str(workspace_id))


async def validate_evaluation_target(
    *, repositories: EvaluationRepositories, tenant_id: UUID, target_id: UUID
) -> None:
    target = await repositories.evaluation_targets.get_by_id(
        tenant_id=tenant_id, target_id=target_id
    )
    if target is None:
        raise ReferencedEvaluationTargetNotFoundError(str(target_id))
