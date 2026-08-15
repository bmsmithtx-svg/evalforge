"""Tenant-membership read use cases.

``list_tenant_members`` is the one place that checks the central
``TenantAction`` permission table before returning other members' data
— routes never compare ``context.role`` themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.identity import IdentityRepositories, MembershipRecord, TenantRecord


class AuthorizationDeniedError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class TenantMembershipSummary:
    tenant: TenantRecord
    membership: MembershipRecord


async def list_my_tenants(
    *, user_id: UUID, repositories: IdentityRepositories
) -> tuple[TenantMembershipSummary, ...]:
    memberships = await repositories.memberships.list_for_user(user_id)
    summaries: list[TenantMembershipSummary] = []
    for membership in memberships:
        tenant = await repositories.tenants.get_by_id(membership.tenant_id)
        if tenant is not None:
            summaries.append(TenantMembershipSummary(tenant=tenant, membership=membership))
    return tuple(summaries)


async def list_tenant_members(
    *, context: TenantContext, repositories: IdentityRepositories
) -> tuple[MembershipRecord, ...]:
    if not context.can(TenantAction.LIST_TENANT_MEMBERS):
        emit_audit_event(
            event="tenant_membership_list",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to list tenant members.")

    members = await repositories.memberships.list_for_tenant(
        tenant_id=context.tenant_id, requesting_user_id=context.user_id
    )
    emit_audit_event(
        event="tenant_membership_list",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
    )
    return members
