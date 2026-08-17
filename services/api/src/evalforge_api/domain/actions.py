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

    # Milestone 4: versioned evaluation domain and persistence.
    CREATE_WORKSPACE = "create_workspace"
    VIEW_WORKSPACE = "view_workspace"
    CREATE_EVALUATION_TARGET = "create_evaluation_target"
    VIEW_EVALUATION_TARGET = "view_evaluation_target"
    CREATE_VERSIONED_RESOURCE = "create_versioned_resource"
    VIEW_VERSIONED_RESOURCE = "view_versioned_resource"
    CREATE_DATASET = "create_dataset"
    VIEW_DATASET = "view_dataset"
    CREATE_TEST_CASE = "create_test_case"
    VIEW_DATASET_SNAPSHOT = "view_dataset_snapshot"
    FINALIZE_DATASET_SNAPSHOT = "finalize_dataset_snapshot"
    CREATE_ARTIFACT = "create_artifact"
    VIEW_ARTIFACT = "view_artifact"

    # Milestone 5: SDK, API, trace, and run ingestion.
    INGEST_RUN = "ingest_run"
    VIEW_RUN = "view_run"
    INGEST_TRACE = "ingest_trace"
    VIEW_TRACE = "view_trace"

    # Milestone 6: dataset and test-case management. Read paths
    # (list, get, history, compare, sample, export, duplicate check)
    # deliberately reuse VIEW_DATASET / VIEW_DATASET_SNAPSHOT rather
    # than adding view-only actions, matching the existing "every role
    # may view evaluation evidence" convention above.
    UPDATE_DATASET = "update_dataset"
    ARCHIVE_DATASET = "archive_dataset"
    CLONE_DATASET = "clone_dataset"
    IMPORT_TEST_CASES = "import_test_cases"


# Milestone 4 read-only actions every membership role may perform: a
# reviewer or read-only observer needs to see evidence (targets,
# versioned configuration, datasets, snapshots, artifacts) even though
# only developer and evaluation-engineer roles may create or version
# it, per docs/TENANCY_AND_AUTHORIZATION.md's role descriptions.
_EVALUATION_DOMAIN_VIEW_ACTIONS: frozenset[TenantAction] = frozenset(
    {
        TenantAction.VIEW_WORKSPACE,
        TenantAction.VIEW_EVALUATION_TARGET,
        TenantAction.VIEW_VERSIONED_RESOURCE,
        TenantAction.VIEW_DATASET,
        TenantAction.VIEW_DATASET_SNAPSHOT,
        TenantAction.VIEW_ARTIFACT,
        TenantAction.VIEW_RUN,
        TenantAction.VIEW_TRACE,
    }
)

# "Manages target configurations" and "submits runs and traces"
# (docs/TENANCY_AND_AUTHORIZATION.md): developer owns evaluation
# targets, the versioned model/prompt/retrieval/tool/workflow
# configuration attached to them, and ingested execution evidence.
_DEVELOPER_MUTATIONS: frozenset[TenantAction] = frozenset(
    {
        TenantAction.CREATE_EVALUATION_TARGET,
        TenantAction.CREATE_VERSIONED_RESOURCE,
        TenantAction.CREATE_ARTIFACT,
        TenantAction.INGEST_RUN,
        TenantAction.INGEST_TRACE,
    }
)

# "Creates and manages datasets, evaluators, ... comparisons, and
# reports" (docs/TENANCY_AND_AUTHORIZATION.md): evaluation engineer
# owns dataset/test-case authoring, snapshot finalization, evaluator
# versioning, and artifact creation.
_EVALUATION_ENGINEER_MUTATIONS: frozenset[TenantAction] = frozenset(
    {
        TenantAction.CREATE_VERSIONED_RESOURCE,
        TenantAction.CREATE_DATASET,
        TenantAction.CREATE_TEST_CASE,
        TenantAction.FINALIZE_DATASET_SNAPSHOT,
        TenantAction.CREATE_ARTIFACT,
        # Milestone 6: managing a dataset's mutable metadata, its
        # lifecycle, and bulk authoring (clone, import) belongs to the
        # same "creates and manages datasets" ownership as authoring
        # individual test cases. tenant_admin inherits all of these
        # through the set union in _ROLE_PERMISSIONS below.
        TenantAction.UPDATE_DATASET,
        TenantAction.ARCHIVE_DATASET,
        TenantAction.CLONE_DATASET,
        TenantAction.IMPORT_TEST_CASES,
    }
)

_ROLE_PERMISSIONS: dict[TenantRole, frozenset[TenantAction]] = {
    TenantRole.TENANT_ADMIN: frozenset(
        {
            TenantAction.VIEW_TENANT_CONTEXT,
            TenantAction.LIST_TENANT_MEMBERS,
            # No workspace-administrator role exists yet (see
            # docs/TENANCY_AND_AUTHORIZATION.md); tenant_admin is the
            # only role that may create the workspace container until
            # one is added.
            TenantAction.CREATE_WORKSPACE,
        }
        | _EVALUATION_DOMAIN_VIEW_ACTIONS
        | _DEVELOPER_MUTATIONS
        | _EVALUATION_ENGINEER_MUTATIONS
    ),
    TenantRole.EVALUATION_ENGINEER: frozenset(
        {TenantAction.VIEW_TENANT_CONTEXT}
        | _EVALUATION_DOMAIN_VIEW_ACTIONS
        | _EVALUATION_ENGINEER_MUTATIONS
    ),
    TenantRole.DEVELOPER: frozenset(
        {TenantAction.VIEW_TENANT_CONTEXT} | _EVALUATION_DOMAIN_VIEW_ACTIONS | _DEVELOPER_MUTATIONS
    ),
    TenantRole.REVIEWER: frozenset(
        {TenantAction.VIEW_TENANT_CONTEXT} | _EVALUATION_DOMAIN_VIEW_ACTIONS
    ),
    TenantRole.READ_ONLY_OBSERVER: frozenset(
        {TenantAction.VIEW_TENANT_CONTEXT} | _EVALUATION_DOMAIN_VIEW_ACTIONS
    ),
}


def role_can(role: TenantRole, action: TenantAction) -> bool:
    """Deny-by-default: an undefined role or action grants nothing."""
    return action in _ROLE_PERMISSIONS.get(role, frozenset())
