from __future__ import annotations

import pytest

from evalforge_api.domain.actions import TenantAction, role_can
from evalforge_api.domain.enums import TenantRole

_MILESTONE_6_MUTATIONS = (
    TenantAction.UPDATE_DATASET,
    TenantAction.ARCHIVE_DATASET,
    TenantAction.CLONE_DATASET,
    TenantAction.IMPORT_TEST_CASES,
)
_DATASET_READ_ACTIONS = (TenantAction.VIEW_DATASET, TenantAction.VIEW_DATASET_SNAPSHOT)


@pytest.mark.parametrize("action", _MILESTONE_6_MUTATIONS)
def test_evaluation_engineer_may_perform_every_dataset_management_mutation(
    action: TenantAction,
) -> None:
    assert role_can(TenantRole.EVALUATION_ENGINEER, action) is True


@pytest.mark.parametrize("action", _MILESTONE_6_MUTATIONS)
def test_tenant_admin_inherits_every_dataset_management_mutation(action: TenantAction) -> None:
    assert role_can(TenantRole.TENANT_ADMIN, action) is True


@pytest.mark.parametrize("action", _MILESTONE_6_MUTATIONS)
@pytest.mark.parametrize("role", [TenantRole.REVIEWER, TenantRole.READ_ONLY_OBSERVER])
def test_read_only_roles_may_not_perform_any_dataset_management_mutation(
    role: TenantRole, action: TenantAction
) -> None:
    assert role_can(role, action) is False


@pytest.mark.parametrize("action", _MILESTONE_6_MUTATIONS)
def test_developer_does_not_manage_datasets(action: TenantAction) -> None:
    """Dataset ownership belongs to the evaluation engineer, matching
    the Milestone 4 split for CREATE_DATASET / CREATE_TEST_CASE."""
    assert role_can(TenantRole.DEVELOPER, action) is False


@pytest.mark.parametrize("action", _DATASET_READ_ACTIONS)
def test_every_role_may_still_read_datasets_and_snapshots(action: TenantAction) -> None:
    for role in TenantRole:
        assert role_can(role, action) is True, f"{role} should be able to {action}"


def test_no_view_only_action_was_added_for_milestone_6() -> None:
    """Read paths reuse VIEW_DATASET / VIEW_DATASET_SNAPSHOT; a new
    view action would silently exclude existing roles."""
    view_actions = {action for action in TenantAction if action.value.startswith("view_")}
    assert view_actions == {
        TenantAction.VIEW_TENANT_CONTEXT,
        TenantAction.VIEW_WORKSPACE,
        TenantAction.VIEW_EVALUATION_TARGET,
        TenantAction.VIEW_VERSIONED_RESOURCE,
        TenantAction.VIEW_DATASET,
        TenantAction.VIEW_DATASET_SNAPSHOT,
        TenantAction.VIEW_ARTIFACT,
        TenantAction.VIEW_RUN,
        TenantAction.VIEW_TRACE,
    }


def test_an_unknown_role_is_denied_every_dataset_management_action() -> None:
    for action in _MILESTONE_6_MUTATIONS + _DATASET_READ_ACTIONS:
        assert role_can("not-a-real-role", action) is False  # type: ignore[arg-type]
