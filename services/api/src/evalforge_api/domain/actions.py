"""Central authorization policy: which role may perform which action.

Route handlers and application services must ask this module rather
than compare ``role`` strings inline, so permission logic has exactly
one place to change and one place to audit.
"""

from __future__ import annotations

from enum import StrEnum

from evalforge_api.domain.enums import TenantRole


class TenantAction(StrEnum):
    VIEW_TENANT_CONTEXT = "view_tenant_context"
    LIST_TENANT_MEMBERS = "list_tenant_members"


_ROLE_PERMISSIONS: dict[TenantRole, frozenset[TenantAction]] = {
    TenantRole.TENANT_ADMIN: frozenset(
        {TenantAction.VIEW_TENANT_CONTEXT, TenantAction.LIST_TENANT_MEMBERS}
    ),
    TenantRole.EVALUATION_ENGINEER: frozenset({TenantAction.VIEW_TENANT_CONTEXT}),
    TenantRole.DEVELOPER: frozenset({TenantAction.VIEW_TENANT_CONTEXT}),
    TenantRole.REVIEWER: frozenset({TenantAction.VIEW_TENANT_CONTEXT}),
    TenantRole.READ_ONLY_OBSERVER: frozenset({TenantAction.VIEW_TENANT_CONTEXT}),
}


def role_can(role: TenantRole, action: TenantAction) -> bool:
    """Deny-by-default: an undefined role or action grants nothing."""
    return action in _ROLE_PERMISSIONS.get(role, frozenset())
