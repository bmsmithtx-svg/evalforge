"""Versioned evaluation-configuration resource use cases.

Covers the seven kinds of versioned configuration fixed by the domain
model — model, prompt, retrieval, tool, workflow, evaluator, and
pricing versions (``evalforge_api.domain.evaluation_enums.ResourceKind``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.evaluation_enums import ResourceKind
from evalforge_api.domain.hashing import (
    CANONICALIZATION_VERSION,
    HASH_ALGORITHM,
    hash_canonical_content,
)
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.domain.versioning import next_version_number, validate_lineage_within_resource
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.versioned_resources import (
    VersionedResourceRecord,
    VersionedResourceVersionRecord,
)


class AuthorizationDeniedError(Exception):
    pass


class ResourceNotFoundError(Exception):
    pass


async def create_resource(
    *,
    context: TenantContext,
    workspace_id: UUID,
    kind: ResourceKind,
    name: str,
    repositories: EvaluationRepositories,
) -> VersionedResourceRecord:
    if not context.can(TenantAction.CREATE_VERSIONED_RESOURCE):
        emit_audit_event(
            event="versioned_resource_creation",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
            kind=kind.value,
        )
        raise AuthorizationDeniedError("Not authorized to create a versioned resource.")

    resource = await repositories.versioned_resources.create_resource(
        tenant_id=context.tenant_id,
        workspace_id=workspace_id,
        kind=kind,
        name=name,
        created_by=context.user_id,
    )
    emit_audit_event(
        event="versioned_resource_creation",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        resource_id=str(resource.id),
        kind=kind.value,
    )
    return resource


async def create_version(
    *,
    context: TenantContext,
    resource_id: UUID,
    content: dict[str, Any],
    derived_from_version_id: UUID | None,
    repositories: EvaluationRepositories,
) -> VersionedResourceVersionRecord:
    """Create a new immutable version of ``resource_id``.

    Always inserts a new row; existing versions are never rewritten
    (docs/adr/0002-versioned-artifacts-and-immutable-run-snapshots.md).
    """
    if not context.can(TenantAction.CREATE_VERSIONED_RESOURCE):
        emit_audit_event(
            event="versioned_resource_version_creation",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to create a versioned resource version.")

    resource = await repositories.versioned_resources.get_resource(
        tenant_id=context.tenant_id, resource_id=resource_id
    )
    if resource is None:
        raise ResourceNotFoundError(str(resource_id))

    existing_versions = await repositories.versioned_resources.list_versions(
        tenant_id=context.tenant_id, resource_id=resource_id
    )

    if derived_from_version_id is not None:
        derived_from = await repositories.versioned_resources.get_version(
            tenant_id=context.tenant_id, version_id=derived_from_version_id
        )
        if derived_from is None:
            raise ResourceNotFoundError(str(derived_from_version_id))
        validate_lineage_within_resource(
            version_resource_id=resource_id, derived_from_resource_id=derived_from.resource_id
        )

    version_number = next_version_number(v.version_number for v in existing_versions)
    content_hash = hash_canonical_content(content)

    version = await repositories.versioned_resources.create_version(
        tenant_id=context.tenant_id,
        resource_id=resource_id,
        version_number=version_number,
        content=content,
        content_hash=content_hash,
        hash_algorithm=HASH_ALGORITHM,
        canonicalization_version=CANONICALIZATION_VERSION,
        derived_from_version_id=derived_from_version_id,
        created_by=context.user_id,
    )
    emit_audit_event(
        event="versioned_resource_version_creation",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        resource_id=str(resource_id),
        version_id=str(version.id),
        version_number=version_number,
    )
    return version
