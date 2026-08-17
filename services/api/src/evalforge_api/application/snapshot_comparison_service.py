"""Compare the frozen membership of two dataset snapshots.

Answers the question a reviewer asks when two runs disagree: what
actually changed in the dataset between them? The comparison itself is
pure (``evalforge_api.domain.snapshot_comparison``); this service only
loads tenant-scoped membership and authorizes the read.

Existence disclosure: both snapshots are resolved through
tenant-scoped repository calls, so a snapshot belonging to another
tenant is simply absent. When either side is absent the caller gets one
undifferentiated not-found error — the response never reveals *which*
of the two IDs resolved, so it cannot be used as an existence oracle
(docs/TENANCY_AND_AUTHORIZATION.md, docs/THREAT_MODEL.md).
"""

from __future__ import annotations

from uuid import UUID

from evalforge_api.application.dataset_errors import (
    AuthorizationDeniedError,
    SnapshotNotFoundError,
)
from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.snapshot_comparison import (
    SnapshotComparisonResult,
    SnapshotMembershipEntry,
    compare_snapshot_membership,
)
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories

_NOT_FOUND_MESSAGE = "One or both dataset snapshots were not found."


async def load_membership(
    *, context: TenantContext, snapshot_id: UUID, repositories: EvaluationRepositories
) -> tuple[SnapshotMembershipEntry, ...] | None:
    """Frozen membership of one snapshot, or ``None`` when the snapshot
    is not visible to the caller's tenant."""
    snapshot = await repositories.snapshots.get_snapshot(
        tenant_id=context.tenant_id, snapshot_id=snapshot_id
    )
    if snapshot is None:
        return None

    items = await repositories.snapshots.list_items(
        tenant_id=context.tenant_id, snapshot_id=snapshot_id
    )
    entries: list[SnapshotMembershipEntry] = []
    for item in items:
        version = await repositories.datasets.get_test_case_version(
            tenant_id=context.tenant_id, version_id=item.test_case_version_id
        )
        assert version is not None  # guaranteed by the composite tenant FK
        entries.append(
            SnapshotMembershipEntry(
                test_case_id=version.test_case_id,
                test_case_version_id=version.id,
                version_number=version.version_number,
                content_hash=version.content_hash,
            )
        )
    return tuple(entries)


async def compare_snapshots(
    *,
    context: TenantContext,
    left_snapshot_id: UUID,
    right_snapshot_id: UUID,
    repositories: EvaluationRepositories,
) -> SnapshotComparisonResult:
    if not context.can(TenantAction.VIEW_DATASET_SNAPSHOT):
        emit_audit_event(
            event="dataset_snapshot_comparison",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to compare dataset snapshots.")

    left = await load_membership(
        context=context, snapshot_id=left_snapshot_id, repositories=repositories
    )
    right = await load_membership(
        context=context, snapshot_id=right_snapshot_id, repositories=repositories
    )
    if left is None or right is None:
        raise SnapshotNotFoundError(_NOT_FOUND_MESSAGE)

    result = compare_snapshot_membership(left, right)
    emit_audit_event(
        event="dataset_snapshot_comparison",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        left_snapshot_id=str(left_snapshot_id),
        right_snapshot_id=str(right_snapshot_id),
        added_count=len(result.added),
        removed_count=len(result.removed),
        changed_count=len(result.changed),
    )
    return result
