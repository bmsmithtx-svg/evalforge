"""Immutable dataset-snapshot construction and finalization use cases.

A draft snapshot accumulates membership via ``add_test_case_version``;
``finalize_snapshot`` freezes membership, computes the content hash
over the frozen membership, and — via the database trigger on
``dataset_snapshots`` — makes the snapshot row itself immutable to any
further update. See docs/adr/0002 and docs/REPRODUCIBILITY_CONTRACT.md.
"""

from __future__ import annotations

from uuid import UUID

from evalforge_api.adapters.dataset_snapshot_repository import SnapshotNotDraftError
from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.hashing import (
    CANONICALIZATION_VERSION,
    HASH_ALGORITHM,
    hash_canonical_content,
)
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.domain.versioning import ensure_snapshot_is_draft
from evalforge_api.ports.datasets import DatasetSnapshotRecord
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories

__all__ = [
    "AuthorizationDeniedError",
    "SnapshotNotDraftError",
    "SnapshotNotFoundError",
    "add_test_case_version",
    "create_draft_snapshot",
    "finalize_snapshot",
]


class AuthorizationDeniedError(Exception):
    pass


class SnapshotNotFoundError(Exception):
    pass


async def create_draft_snapshot(
    *, context: TenantContext, dataset_id: UUID, repositories: EvaluationRepositories
) -> DatasetSnapshotRecord:
    if not context.can(TenantAction.FINALIZE_DATASET_SNAPSHOT):
        emit_audit_event(
            event="dataset_snapshot_draft_creation",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to create a dataset snapshot.")

    snapshot = await repositories.snapshots.create_draft(
        tenant_id=context.tenant_id, dataset_id=dataset_id, created_by=context.user_id
    )
    emit_audit_event(
        event="dataset_snapshot_draft_creation",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        snapshot_id=str(snapshot.id),
    )
    return snapshot


async def add_test_case_version(
    *,
    context: TenantContext,
    snapshot_id: UUID,
    test_case_version_id: UUID,
    sequence_index: int,
    repositories: EvaluationRepositories,
) -> None:
    if not context.can(TenantAction.FINALIZE_DATASET_SNAPSHOT):
        emit_audit_event(
            event="dataset_snapshot_item_addition",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to modify a dataset snapshot.")

    try:
        await repositories.snapshots.add_item(
            tenant_id=context.tenant_id,
            snapshot_id=snapshot_id,
            test_case_version_id=test_case_version_id,
            sequence_index=sequence_index,
        )
    except SnapshotNotDraftError:
        emit_audit_event(
            event="dataset_snapshot_item_addition",
            outcome="denied_immutable",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            snapshot_id=str(snapshot_id),
        )
        raise

    emit_audit_event(
        event="dataset_snapshot_item_addition",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        snapshot_id=str(snapshot_id),
        test_case_version_id=str(test_case_version_id),
    )


async def finalize_snapshot(
    *, context: TenantContext, snapshot_id: UUID, repositories: EvaluationRepositories
) -> DatasetSnapshotRecord:
    if not context.can(TenantAction.FINALIZE_DATASET_SNAPSHOT):
        emit_audit_event(
            event="dataset_snapshot_finalization",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to finalize a dataset snapshot.")

    snapshot = await repositories.snapshots.get_snapshot(
        tenant_id=context.tenant_id, snapshot_id=snapshot_id
    )
    if snapshot is None:
        raise SnapshotNotFoundError(str(snapshot_id))
    ensure_snapshot_is_draft(snapshot.status)

    items = await repositories.snapshots.list_items(
        tenant_id=context.tenant_id, snapshot_id=snapshot_id
    )

    membership_entries = []
    for item in items:
        version = await repositories.datasets.get_test_case_version(
            tenant_id=context.tenant_id, version_id=item.test_case_version_id
        )
        assert version is not None  # guaranteed by the composite tenant FK
        membership_entries.append(
            {
                "sequence_index": item.sequence_index,
                "test_case_id": str(version.test_case_id),
                "test_case_version_id": str(item.test_case_version_id),
                "test_case_version_number": version.version_number,
                "test_case_content_hash": version.content_hash,
            }
        )

    content_hash = hash_canonical_content(
        {"dataset_id": str(snapshot.dataset_id), "items": membership_entries}
    )

    finalized = await repositories.snapshots.finalize(
        tenant_id=context.tenant_id,
        snapshot_id=snapshot_id,
        content_hash=content_hash,
        hash_algorithm=HASH_ALGORITHM,
        canonicalization_version=CANONICALIZATION_VERSION,
        item_count=len(items),
        finalized_by=context.user_id,
    )
    emit_audit_event(
        event="dataset_snapshot_finalization",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        snapshot_id=str(snapshot_id),
        content_hash=content_hash,
        item_count=len(items),
    )
    return finalized
