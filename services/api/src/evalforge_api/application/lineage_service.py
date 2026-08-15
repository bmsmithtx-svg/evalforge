"""Read-only lineage queries across the evaluation domain.

Answers "which logical resource does this version belong to," "which
version did this derive from," "which dataset does this snapshot
belong to," and "which test-case versions are frozen into this
snapshot" — the lineage questions Milestone 4 must be able to answer
per docs/DOMAIN_MODEL.md.
"""

from __future__ import annotations

from uuid import UUID

from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.artifacts import ArtifactVersionRecord
from evalforge_api.ports.datasets import DatasetSnapshotItemRecord
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.versioned_resources import VersionedResourceVersionRecord


class AuthorizationDeniedError(Exception):
    pass


class LineageNotFoundError(Exception):
    pass


async def resource_version_ancestry(
    *, context: TenantContext, version_id: UUID, repositories: EvaluationRepositories
) -> tuple[VersionedResourceVersionRecord, ...]:
    """The chain from ``version_id`` back to its earliest ancestor,
    most recent first."""
    if not context.can(TenantAction.VIEW_VERSIONED_RESOURCE):
        raise AuthorizationDeniedError("Not authorized to view this resource's lineage.")

    chain: list[VersionedResourceVersionRecord] = []
    current_id: UUID | None = version_id
    while current_id is not None:
        version = await repositories.versioned_resources.get_version(
            tenant_id=context.tenant_id, version_id=current_id
        )
        if version is None:
            if not chain:
                raise LineageNotFoundError(str(version_id))
            break
        chain.append(version)
        current_id = version.derived_from_version_id
    return tuple(chain)


async def artifact_version_ancestry(
    *, context: TenantContext, version_id: UUID, repositories: EvaluationRepositories
) -> tuple[ArtifactVersionRecord, ...]:
    """The chain from ``version_id`` back to its earliest ancestor,
    most recent first."""
    if not context.can(TenantAction.VIEW_ARTIFACT):
        raise AuthorizationDeniedError("Not authorized to view this artifact's lineage.")

    chain: list[ArtifactVersionRecord] = []
    current_id: UUID | None = version_id
    while current_id is not None:
        version = await repositories.artifacts.get_artifact_version(
            tenant_id=context.tenant_id, version_id=current_id
        )
        if version is None:
            if not chain:
                raise LineageNotFoundError(str(version_id))
            break
        chain.append(version)
        current_id = version.derived_from_artifact_version_id
    return tuple(chain)


async def snapshot_membership(
    *, context: TenantContext, snapshot_id: UUID, repositories: EvaluationRepositories
) -> tuple[DatasetSnapshotItemRecord, ...]:
    if not context.can(TenantAction.VIEW_DATASET_SNAPSHOT):
        raise AuthorizationDeniedError("Not authorized to view this snapshot's membership.")

    snapshot = await repositories.snapshots.get_snapshot(
        tenant_id=context.tenant_id, snapshot_id=snapshot_id
    )
    if snapshot is None:
        raise LineageNotFoundError(str(snapshot_id))
    return await repositories.snapshots.list_items(
        tenant_id=context.tenant_id, snapshot_id=snapshot_id
    )
