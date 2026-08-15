from __future__ import annotations

from uuid import uuid4

from evalforge_api.domain.actions import TenantAction, role_can
from evalforge_api.domain.enums import MembershipStatus, TenantRole
from evalforge_api.domain.tenant_context import TenantContext


def test_tenant_admin_can_list_members() -> None:
    assert role_can(TenantRole.TENANT_ADMIN, TenantAction.LIST_TENANT_MEMBERS) is True


def test_non_admin_roles_cannot_list_members() -> None:
    for role in (
        TenantRole.EVALUATION_ENGINEER,
        TenantRole.DEVELOPER,
        TenantRole.REVIEWER,
        TenantRole.READ_ONLY_OBSERVER,
    ):
        assert role_can(role, TenantAction.LIST_TENANT_MEMBERS) is False


def test_every_defined_role_can_view_its_own_tenant_context() -> None:
    for role in TenantRole:
        assert role_can(role, TenantAction.VIEW_TENANT_CONTEXT) is True


def test_tenant_context_denies_when_membership_is_not_active() -> None:
    context = TenantContext(
        tenant_id=uuid4(),
        tenant_slug="acme",
        user_id=uuid4(),
        role=TenantRole.TENANT_ADMIN,
        membership_status=MembershipStatus.SUSPENDED,
    )

    assert context.can(TenantAction.VIEW_TENANT_CONTEXT) is False
    assert context.can(TenantAction.LIST_TENANT_MEMBERS) is False


def test_tenant_context_allows_active_admin_to_list_members() -> None:
    context = TenantContext(
        tenant_id=uuid4(),
        tenant_slug="acme",
        user_id=uuid4(),
        role=TenantRole.TENANT_ADMIN,
        membership_status=MembershipStatus.ACTIVE,
    )

    assert context.can(TenantAction.LIST_TENANT_MEMBERS) is True
