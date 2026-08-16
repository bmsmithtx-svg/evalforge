from __future__ import annotations

from evalforge_api.domain.actions import TenantAction, role_can
from evalforge_api.domain.enums import TenantRole

_VIEW_ACTIONS = (TenantAction.VIEW_RUN, TenantAction.VIEW_TRACE)
_INGEST_ACTIONS = (TenantAction.INGEST_RUN, TenantAction.INGEST_TRACE)


def test_every_defined_role_can_view_runs_and_traces() -> None:
    for role in TenantRole:
        for action in _VIEW_ACTIONS:
            assert role_can(role, action) is True, f"{role} should be able to {action}"


def test_only_developer_and_tenant_admin_can_ingest_runs_and_traces() -> None:
    for role in (TenantRole.DEVELOPER, TenantRole.TENANT_ADMIN):
        for action in _INGEST_ACTIONS:
            assert role_can(role, action) is True, f"{role} should be able to {action}"

    for role in (
        TenantRole.EVALUATION_ENGINEER,
        TenantRole.REVIEWER,
        TenantRole.READ_ONLY_OBSERVER,
    ):
        for action in _INGEST_ACTIONS:
            assert role_can(role, action) is False, f"{role} should not be able to {action}"


def test_undefined_action_is_denied_by_default() -> None:
    assert role_can(TenantRole.TENANT_ADMIN, "not_a_real_action") is False  # type: ignore[arg-type]
