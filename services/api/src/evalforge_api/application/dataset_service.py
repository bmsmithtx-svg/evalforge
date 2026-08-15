"""Dataset and test-case authoring use cases."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.hashing import (
    CANONICALIZATION_VERSION,
    HASH_ALGORITHM,
    hash_canonical_content,
)
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.domain.versioning import next_version_number
from evalforge_api.ports.datasets import DatasetRecord, TestCaseRecord, TestCaseVersionRecord
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


class AuthorizationDeniedError(Exception):
    pass


class TestCaseNotFoundError(Exception):
    pass


async def create_dataset(
    *, context: TenantContext, workspace_id: UUID, name: str, repositories: EvaluationRepositories
) -> DatasetRecord:
    if not context.can(TenantAction.CREATE_DATASET):
        emit_audit_event(
            event="dataset_creation",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to create a dataset.")

    dataset = await repositories.datasets.create_dataset(
        tenant_id=context.tenant_id,
        workspace_id=workspace_id,
        name=name,
        created_by=context.user_id,
    )
    emit_audit_event(
        event="dataset_creation",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        dataset_id=str(dataset.id),
    )
    return dataset


async def create_test_case(
    *,
    context: TenantContext,
    dataset_id: UUID,
    external_key: str | None,
    repositories: EvaluationRepositories,
) -> TestCaseRecord:
    if not context.can(TenantAction.CREATE_TEST_CASE):
        emit_audit_event(
            event="test_case_creation",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to create a test case.")

    test_case = await repositories.datasets.create_test_case(
        tenant_id=context.tenant_id,
        dataset_id=dataset_id,
        external_key=external_key,
        created_by=context.user_id,
    )
    emit_audit_event(
        event="test_case_creation",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        test_case_id=str(test_case.id),
    )
    return test_case


async def create_test_case_version(
    *,
    context: TenantContext,
    test_case_id: UUID,
    content: dict[str, Any],
    repositories: EvaluationRepositories,
) -> TestCaseVersionRecord:
    """Create a new immutable content version for a test case.

    "Editable before snapshot" (docs/DOMAIN_MODEL.md) means a new
    version may always be created — never that an existing version's
    content is rewritten.
    """
    if not context.can(TenantAction.CREATE_TEST_CASE):
        emit_audit_event(
            event="test_case_version_creation",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to create a test-case version.")

    test_case = await repositories.datasets.get_test_case(
        tenant_id=context.tenant_id, test_case_id=test_case_id
    )
    if test_case is None:
        raise TestCaseNotFoundError(str(test_case_id))

    existing_versions = await repositories.datasets.list_test_case_versions(
        tenant_id=context.tenant_id, test_case_id=test_case_id
    )
    version_number = next_version_number(v.version_number for v in existing_versions)
    content_hash = hash_canonical_content(content)

    version = await repositories.datasets.create_test_case_version(
        tenant_id=context.tenant_id,
        test_case_id=test_case_id,
        version_number=version_number,
        content=content,
        content_hash=content_hash,
        hash_algorithm=HASH_ALGORITHM,
        canonicalization_version=CANONICALIZATION_VERSION,
        created_by=context.user_id,
    )
    emit_audit_event(
        event="test_case_version_creation",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        test_case_id=str(test_case_id),
        version_id=str(version.id),
        version_number=version_number,
    )
    return version
