from __future__ import annotations

from evalforge_api.domain.actions import TenantAction, role_can
from evalforge_api.domain.enums import TenantRole

_VIEW_ACTIONS = (
    TenantAction.VIEW_WORKSPACE,
    TenantAction.VIEW_EVALUATION_TARGET,
    TenantAction.VIEW_VERSIONED_RESOURCE,
    TenantAction.VIEW_DATASET,
    TenantAction.VIEW_DATASET_SNAPSHOT,
    TenantAction.VIEW_ARTIFACT,
)


def test_every_defined_role_can_view_every_evaluation_domain_concept() -> None:
    for role in TenantRole:
        for action in _VIEW_ACTIONS:
            assert role_can(role, action) is True, f"{role} should be able to {action}"


def test_only_tenant_admin_can_create_a_workspace() -> None:
    assert role_can(TenantRole.TENANT_ADMIN, TenantAction.CREATE_WORKSPACE) is True
    for role in (
        TenantRole.EVALUATION_ENGINEER,
        TenantRole.DEVELOPER,
        TenantRole.REVIEWER,
        TenantRole.READ_ONLY_OBSERVER,
    ):
        assert role_can(role, TenantAction.CREATE_WORKSPACE) is False


def test_developer_manages_targets_and_configuration_but_not_datasets() -> None:
    assert role_can(TenantRole.DEVELOPER, TenantAction.CREATE_EVALUATION_TARGET) is True
    assert role_can(TenantRole.DEVELOPER, TenantAction.CREATE_VERSIONED_RESOURCE) is True
    assert role_can(TenantRole.DEVELOPER, TenantAction.CREATE_ARTIFACT) is True
    assert role_can(TenantRole.DEVELOPER, TenantAction.CREATE_DATASET) is False
    assert role_can(TenantRole.DEVELOPER, TenantAction.CREATE_TEST_CASE) is False
    assert role_can(TenantRole.DEVELOPER, TenantAction.FINALIZE_DATASET_SNAPSHOT) is False


def test_evaluation_engineer_manages_datasets_and_snapshots_but_not_targets() -> None:
    assert role_can(TenantRole.EVALUATION_ENGINEER, TenantAction.CREATE_DATASET) is True
    assert role_can(TenantRole.EVALUATION_ENGINEER, TenantAction.CREATE_TEST_CASE) is True
    assert role_can(TenantRole.EVALUATION_ENGINEER, TenantAction.FINALIZE_DATASET_SNAPSHOT) is True
    assert role_can(TenantRole.EVALUATION_ENGINEER, TenantAction.CREATE_VERSIONED_RESOURCE) is True
    assert role_can(TenantRole.EVALUATION_ENGINEER, TenantAction.CREATE_EVALUATION_TARGET) is False


def test_reviewer_and_read_only_observer_have_no_evaluation_domain_mutation_rights() -> None:
    mutation_actions = (
        TenantAction.CREATE_WORKSPACE,
        TenantAction.CREATE_EVALUATION_TARGET,
        TenantAction.CREATE_VERSIONED_RESOURCE,
        TenantAction.CREATE_DATASET,
        TenantAction.CREATE_TEST_CASE,
        TenantAction.FINALIZE_DATASET_SNAPSHOT,
        TenantAction.CREATE_ARTIFACT,
    )
    for role in (TenantRole.REVIEWER, TenantRole.READ_ONLY_OBSERVER):
        for action in mutation_actions:
            assert role_can(role, action) is False, f"{role} should not be able to {action}"


def test_tenant_admin_has_every_evaluation_domain_mutation_right() -> None:
    mutation_actions = (
        TenantAction.CREATE_WORKSPACE,
        TenantAction.CREATE_EVALUATION_TARGET,
        TenantAction.CREATE_VERSIONED_RESOURCE,
        TenantAction.CREATE_DATASET,
        TenantAction.CREATE_TEST_CASE,
        TenantAction.FINALIZE_DATASET_SNAPSHOT,
        TenantAction.CREATE_ARTIFACT,
    )
    for action in mutation_actions:
        assert role_can(TenantRole.TENANT_ADMIN, action) is True
