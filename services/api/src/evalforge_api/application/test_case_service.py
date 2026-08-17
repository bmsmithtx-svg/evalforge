"""Test-case authoring and lifecycle use cases.

"Editable before snapshot" (docs/DOMAIN_MODEL.md) means a content
change always creates a *new* immutable ``test_case_versions`` row —
no supported path rewrites an existing version. What is genuinely
mutable about a test case is only its lifecycle and provenance
(``status``, ``archived_at``, ``updated_by``), which is why the
Milestone 6 migration grants UPDATE on ``test_cases`` but not on
``test_case_versions``.

Every content payload is validated through
``evalforge_api.domain.test_case_content`` and fingerprinted for
dataset-scoped duplicate detection through
``evalforge_api.domain.duplicate_detection`` before it reaches the
repository. The caller's original JSON is what gets stored, so content
hashes stay stable for content authored before this schema existed and
no key is silently dropped from storage.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from evalforge_api.application.dataset_errors import (
    AuthorizationDeniedError,
    TestCaseNotFoundError,
)
from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.duplicate_detection import compute_dedup_hash
from evalforge_api.domain.evaluation_enums import TestCaseStatus
from evalforge_api.domain.hashing import (
    CANONICALIZATION_VERSION,
    HASH_ALGORITHM,
    hash_canonical_content,
)
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.domain.test_case_content import TestCaseContent
from evalforge_api.domain.versioning import next_version_number
from evalforge_api.ports.datasets import TestCaseRecord, TestCaseVersionRecord
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


def _deny(event: str, context: TenantContext, message: str) -> None:
    emit_audit_event(
        event=event,
        outcome="denied",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        role=context.role.value,
    )
    raise AuthorizationDeniedError(message)


async def create_test_case(
    *,
    context: TenantContext,
    dataset_id: UUID,
    external_key: str | None,
    repositories: EvaluationRepositories,
) -> TestCaseRecord:
    if not context.can(TenantAction.CREATE_TEST_CASE):
        _deny("test_case_creation", context, "Not authorized to create a test case.")

    test_case = await repositories.datasets.create_test_case(
        tenant_id=context.tenant_id,
        dataset_id=dataset_id,
        external_key=external_key,
        source="manual",
        source_test_case_id=None,
        import_batch_id=None,
        created_by=context.user_id,
    )
    emit_audit_event(
        event="test_case_creation",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        dataset_id=str(dataset_id),
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
    """Create a new immutable content version for a test case."""
    if not context.can(TenantAction.CREATE_TEST_CASE):
        _deny(
            "test_case_version_creation", context, "Not authorized to create a test-case version."
        )

    test_case = await repositories.datasets.get_test_case(
        tenant_id=context.tenant_id, test_case_id=test_case_id
    )
    if test_case is None:
        raise TestCaseNotFoundError(str(test_case_id))

    typed_content = TestCaseContent.from_json_dict(content)
    existing_versions = await repositories.datasets.list_test_case_versions(
        tenant_id=context.tenant_id, test_case_id=test_case_id
    )
    version_number = next_version_number(v.version_number for v in existing_versions)

    version = await repositories.datasets.create_test_case_version(
        tenant_id=context.tenant_id,
        test_case_id=test_case_id,
        version_number=version_number,
        content=content,
        content_hash=hash_canonical_content(content),
        dedup_hash=compute_dedup_hash(typed_content),
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


async def get_test_case(
    *, context: TenantContext, test_case_id: UUID, repositories: EvaluationRepositories
) -> TestCaseRecord:
    if not context.can(TenantAction.VIEW_DATASET):
        raise AuthorizationDeniedError("Not authorized to view this test case.")
    test_case = await repositories.datasets.get_test_case(
        tenant_id=context.tenant_id, test_case_id=test_case_id
    )
    if test_case is None:
        raise TestCaseNotFoundError(str(test_case_id))
    return test_case


async def list_test_cases(
    *,
    context: TenantContext,
    dataset_id: UUID,
    status: TestCaseStatus | None,
    repositories: EvaluationRepositories,
) -> tuple[TestCaseRecord, ...]:
    if not context.can(TenantAction.VIEW_DATASET):
        raise AuthorizationDeniedError("Not authorized to view test cases.")
    return await repositories.datasets.list_test_cases(
        tenant_id=context.tenant_id, dataset_id=dataset_id, status=status
    )


async def get_test_case_history(
    *, context: TenantContext, test_case_id: UUID, repositories: EvaluationRepositories
) -> tuple[TestCaseVersionRecord, ...]:
    """Every content version of a test case, oldest first. History is
    append-only, so this is the complete audit trail of the case."""
    if not context.can(TenantAction.VIEW_DATASET):
        raise AuthorizationDeniedError("Not authorized to view test-case history.")
    test_case = await repositories.datasets.get_test_case(
        tenant_id=context.tenant_id, test_case_id=test_case_id
    )
    if test_case is None:
        raise TestCaseNotFoundError(str(test_case_id))
    return await repositories.datasets.list_test_case_versions(
        tenant_id=context.tenant_id, test_case_id=test_case_id
    )


async def archive_test_case(
    *, context: TenantContext, test_case_id: UUID, repositories: EvaluationRepositories
) -> TestCaseRecord:
    """Archival never deletes: the row, every version, and every
    snapshot that froze one of those versions are untouched."""
    if not context.can(TenantAction.ARCHIVE_DATASET):
        _deny("test_case_archival", context, "Not authorized to archive a test case.")

    archived = await repositories.datasets.archive_test_case(
        tenant_id=context.tenant_id, test_case_id=test_case_id, updated_by=context.user_id
    )
    if archived is None:
        raise TestCaseNotFoundError(str(test_case_id))
    emit_audit_event(
        event="test_case_archival",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        test_case_id=str(test_case_id),
    )
    return archived
