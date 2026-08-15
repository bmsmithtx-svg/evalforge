"""Workspace and evaluation-target creation use cases.

Workspace-scoped authorization does not exist yet
(docs/TENANCY_AND_AUTHORIZATION.md); every check here is against the
tenant-level ``TenantContext`` only.
"""

from __future__ import annotations

from uuid import UUID

from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.workspaces import EvaluationTargetRecord, WorkspaceRecord


class AuthorizationDeniedError(Exception):
    pass


async def create_workspace(
    *, context: TenantContext, slug: str, name: str, repositories: EvaluationRepositories
) -> WorkspaceRecord:
    if not context.can(TenantAction.CREATE_WORKSPACE):
        emit_audit_event(
            event="workspace_creation",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to create a workspace.")

    workspace = await repositories.workspaces.create(
        tenant_id=context.tenant_id, slug=slug, name=name, created_by=context.user_id
    )
    emit_audit_event(
        event="workspace_creation",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        workspace_id=str(workspace.id),
    )
    return workspace


async def create_evaluation_target(
    *,
    context: TenantContext,
    workspace_id: UUID,
    name: str,
    target_type: str,
    repositories: EvaluationRepositories,
) -> EvaluationTargetRecord:
    if not context.can(TenantAction.CREATE_EVALUATION_TARGET):
        emit_audit_event(
            event="evaluation_target_creation",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to create an evaluation target.")

    target = await repositories.evaluation_targets.create(
        tenant_id=context.tenant_id,
        workspace_id=workspace_id,
        name=name,
        target_type=target_type,
        created_by=context.user_id,
    )
    emit_audit_event(
        event="evaluation_target_creation",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        evaluation_target_id=str(target.id),
    )
    return target
