"""Artifact content persistence and verification use cases.

Bytes go to S3-compatible object storage under a tenant-scoped key;
PostgreSQL holds only metadata, hash, and lineage. The storage key is
always derived here from server-verified tenant identity plus the
computed content hash — never from caller input — so no request can
influence where bytes land or let one tenant's request touch another
tenant's object.
"""

from __future__ import annotations

from uuid import UUID

from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.hashing import HASH_ALGORITHM, hash_bytes
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.domain.versioning import next_version_number
from evalforge_api.ports.artifacts import ArtifactRecord, ArtifactVersionRecord
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


class AuthorizationDeniedError(Exception):
    pass


class ArtifactNotFoundError(Exception):
    pass


class ArtifactHashMismatchError(Exception):
    """Raised when retrieved bytes no longer match their recorded hash."""


def _storage_key(
    *, tenant_id: UUID, artifact_id: UUID, version_number: int, content_hash: str
) -> str:
    return f"tenants/{tenant_id}/artifacts/{artifact_id}/versions/{version_number}-{content_hash}"


async def create_artifact(
    *,
    context: TenantContext,
    workspace_id: UUID | None,
    media_type: str,
    purpose: str,
    repositories: EvaluationRepositories,
) -> ArtifactRecord:
    if not context.can(TenantAction.CREATE_ARTIFACT):
        emit_audit_event(
            event="artifact_creation",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to create an artifact.")

    artifact = await repositories.artifacts.create_artifact(
        tenant_id=context.tenant_id,
        workspace_id=workspace_id,
        media_type=media_type,
        purpose=purpose,
        created_by=context.user_id,
    )
    emit_audit_event(
        event="artifact_creation",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        artifact_id=str(artifact.id),
    )
    return artifact


async def store_artifact_version(
    *,
    context: TenantContext,
    artifact_id: UUID,
    body: bytes,
    content_type: str,
    derived_from_artifact_version_id: UUID | None,
    repositories: EvaluationRepositories,
) -> ArtifactVersionRecord:
    if not context.can(TenantAction.CREATE_ARTIFACT):
        emit_audit_event(
            event="artifact_version_creation",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to store an artifact version.")

    artifact = await repositories.artifacts.get_artifact(
        tenant_id=context.tenant_id, artifact_id=artifact_id
    )
    if artifact is None:
        raise ArtifactNotFoundError(str(artifact_id))

    existing_versions = await repositories.artifacts.list_artifact_versions(
        tenant_id=context.tenant_id, artifact_id=artifact_id
    )
    version_number = next_version_number(v.version_number for v in existing_versions)
    content_hash = hash_bytes(body)
    storage_key = _storage_key(
        tenant_id=context.tenant_id,
        artifact_id=artifact_id,
        version_number=version_number,
        content_hash=content_hash,
    )

    await repositories.artifact_storage.put_object(
        key=storage_key, body=body, content_type=content_type
    )

    version = await repositories.artifacts.create_artifact_version(
        tenant_id=context.tenant_id,
        artifact_id=artifact_id,
        version_number=version_number,
        content_hash=content_hash,
        hash_algorithm=HASH_ALGORITHM,
        byte_size=len(body),
        content_type=content_type,
        storage_key=storage_key,
        derived_from_artifact_version_id=derived_from_artifact_version_id,
        created_by=context.user_id,
    )
    emit_audit_event(
        event="artifact_version_creation",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        artifact_id=str(artifact_id),
        version_id=str(version.id),
        content_hash=content_hash,
    )
    return version


async def retrieve_and_verify_artifact_version(
    *, context: TenantContext, version_id: UUID, repositories: EvaluationRepositories
) -> bytes:
    """Fetch bytes and verify them against the recorded content hash.

    A hash mismatch does not silently return unverified bytes — the
    reproducibility contract requires disclosing integrity failures
    rather than masking them (docs/REPRODUCIBILITY_CONTRACT.md).
    """
    if not context.can(TenantAction.VIEW_ARTIFACT):
        emit_audit_event(
            event="artifact_version_retrieval",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to read this artifact.")

    version = await repositories.artifacts.get_artifact_version(
        tenant_id=context.tenant_id, version_id=version_id
    )
    if version is None:
        raise ArtifactNotFoundError(str(version_id))

    body = await repositories.artifact_storage.get_object(key=version.storage_key)
    actual_hash = hash_bytes(body)
    if actual_hash != version.content_hash:
        emit_audit_event(
            event="artifact_version_retrieval",
            outcome="hash_mismatch",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            artifact_version_id=str(version_id),
        )
        raise ArtifactHashMismatchError(str(version_id))

    emit_audit_event(
        event="artifact_version_retrieval",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        artifact_version_id=str(version_id),
    )
    return body
