"""Clone a dataset into a new, independent dataset.

A clone is a *copy*, not a share. Every cloned test case is a brand-new
logical resource in the new dataset, and its content history restarts
at version 1: the two datasets must be able to diverge without either
one's history rewriting the other's. What links them is provenance —
``datasets.source = 'cloned'`` plus ``cloned_from_dataset_id`` /
``cloned_from_snapshot_id``, and ``test_cases.source_test_case_id`` per
case — recorded with composite tenant-scoped foreign keys.

Cloning from a finalized snapshot copies that snapshot's *frozen*
content, which is the reproducible choice. With no snapshot given, the
current latest version of every active test case is copied instead.

The source is resolved through tenant-scoped repository calls, so a
dataset or snapshot belonging to another tenant is simply not found —
there is no second, discriminating ownership check that could turn
this into an existence oracle.
"""

from __future__ import annotations

from uuid import UUID

from evalforge_api.application.dataset_errors import (
    AuthorizationDeniedError,
    DatasetNotFoundError,
    SnapshotNotFoundError,
)
from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.duplicate_detection import compute_dedup_hash
from evalforge_api.domain.hashing import CANONICALIZATION_VERSION, HASH_ALGORITHM
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.domain.test_case_content import TestCaseContent
from evalforge_api.ports.datasets import DatasetRecord, TestCaseSeedRow, TestCaseVersionRecord
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


async def _seed_row(
    *, context: TenantContext, version: TestCaseVersionRecord, repositories: EvaluationRepositories
) -> TestCaseSeedRow:
    source_case = await repositories.datasets.get_test_case(
        tenant_id=context.tenant_id, test_case_id=version.test_case_id
    )
    assert source_case is not None  # guaranteed by the composite tenant FK
    dedup_hash = version.dedup_hash or compute_dedup_hash(
        TestCaseContent.from_json_dict(version.content)
    )
    return TestCaseSeedRow(
        external_key=source_case.external_key,
        content=version.content,
        content_hash=version.content_hash,
        dedup_hash=dedup_hash,
        source_test_case_id=version.test_case_id,
    )


async def _source_versions(
    *,
    context: TenantContext,
    source_dataset_id: UUID,
    source_snapshot_id: UUID | None,
    repositories: EvaluationRepositories,
) -> tuple[TestCaseVersionRecord, ...]:
    if source_snapshot_id is None:
        return await repositories.datasets.list_latest_versions_for_dataset(
            tenant_id=context.tenant_id, dataset_id=source_dataset_id
        )

    snapshot = await repositories.snapshots.get_snapshot(
        tenant_id=context.tenant_id, snapshot_id=source_snapshot_id
    )
    if snapshot is None or snapshot.dataset_id != source_dataset_id:
        raise SnapshotNotFoundError(str(source_snapshot_id))

    items = await repositories.snapshots.list_items(
        tenant_id=context.tenant_id, snapshot_id=source_snapshot_id
    )
    versions: list[TestCaseVersionRecord] = []
    for item in items:
        version = await repositories.datasets.get_test_case_version(
            tenant_id=context.tenant_id, version_id=item.test_case_version_id
        )
        assert version is not None  # guaranteed by the composite tenant FK
        versions.append(version)
    return tuple(versions)


async def clone_dataset(
    *,
    context: TenantContext,
    source_dataset_id: UUID,
    source_snapshot_id: UUID | None,
    new_name: str,
    repositories: EvaluationRepositories,
) -> DatasetRecord:
    if not context.can(TenantAction.CLONE_DATASET):
        emit_audit_event(
            event="dataset_clone",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to clone a dataset.")

    source = await repositories.datasets.get_dataset(
        tenant_id=context.tenant_id, dataset_id=source_dataset_id
    )
    if source is None:
        raise DatasetNotFoundError(str(source_dataset_id))

    versions = await _source_versions(
        context=context,
        source_dataset_id=source_dataset_id,
        source_snapshot_id=source_snapshot_id,
        repositories=repositories,
    )
    seeds = [
        await _seed_row(context=context, version=version, repositories=repositories)
        for version in versions
    ]

    clone = await repositories.datasets.create_dataset(
        tenant_id=context.tenant_id,
        workspace_id=source.workspace_id,
        name=new_name,
        description=source.description,
        tags=source.tags,
        metadata=source.metadata,
        source="cloned",
        cloned_from_dataset_id=source_dataset_id,
        cloned_from_snapshot_id=source_snapshot_id,
        created_by=context.user_id,
    )
    if seeds:
        await repositories.datasets.create_test_cases_with_versions(
            tenant_id=context.tenant_id,
            dataset_id=clone.id,
            rows=seeds,
            source="cloned",
            import_batch_id=None,
            hash_algorithm=HASH_ALGORITHM,
            canonicalization_version=CANONICALIZATION_VERSION,
            created_by=context.user_id,
        )

    emit_audit_event(
        event="dataset_clone",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        source_dataset_id=str(source_dataset_id),
        source_snapshot_id=str(source_snapshot_id) if source_snapshot_id else None,
        dataset_id=str(clone.id),
        cloned_test_case_count=len(seeds),
    )
    return clone
