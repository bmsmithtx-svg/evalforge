"""Deterministic sampling and splitting over a finalized snapshot.

Stateless by design. Nothing is persisted: a sample or a split is a
pure function of (finalized snapshot membership, seed, parameters), so
storing it would add a second, drift-prone source of truth for
something the seed already reproduces exactly. Persisted experiment
structures belong to Milestone 7, not here.

Only *finalized* snapshots may be sampled or split. A draft snapshot's
membership can still change, so the same seed would silently produce a
different sample tomorrow — exactly the non-reproducibility the
platform exists to prevent (docs/REPRODUCIBILITY_CONTRACT.md).
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from evalforge_api.application.dataset_errors import (
    AuthorizationDeniedError,
    SnapshotNotFinalizedError,
    SnapshotNotFoundError,
)
from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.evaluation_enums import DatasetSnapshotStatus
from evalforge_api.domain.sampling import deterministic_sample, deterministic_split
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


async def _finalized_item_ids(
    *, context: TenantContext, snapshot_id: UUID, repositories: EvaluationRepositories
) -> tuple[UUID, ...]:
    if not context.can(TenantAction.VIEW_DATASET_SNAPSHOT):
        raise AuthorizationDeniedError("Not authorized to read this dataset snapshot.")

    snapshot = await repositories.snapshots.get_snapshot(
        tenant_id=context.tenant_id, snapshot_id=snapshot_id
    )
    if snapshot is None:
        raise SnapshotNotFoundError(str(snapshot_id))
    if snapshot.status != DatasetSnapshotStatus.FINALIZED:
        raise SnapshotNotFinalizedError(
            f"Snapshot is '{snapshot.status.value}'; only a finalized snapshot has a stable "
            "membership set that a seed can reproduce."
        )

    items = await repositories.snapshots.list_items(
        tenant_id=context.tenant_id, snapshot_id=snapshot_id
    )
    return tuple(item.test_case_version_id for item in items)


async def sample_snapshot(
    *,
    context: TenantContext,
    snapshot_id: UUID,
    sample_size: int,
    seed: str,
    repositories: EvaluationRepositories,
) -> tuple[UUID, ...]:
    item_ids = await _finalized_item_ids(
        context=context, snapshot_id=snapshot_id, repositories=repositories
    )
    sampled = deterministic_sample(item_ids, sample_size=sample_size, seed=seed)
    emit_audit_event(
        event="dataset_snapshot_sampling",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        snapshot_id=str(snapshot_id),
        sample_size=sample_size,
        population_size=len(item_ids),
    )
    return sampled


async def split_snapshot(
    *,
    context: TenantContext,
    snapshot_id: UUID,
    ratios: Mapping[str, float],
    seed: str,
    repositories: EvaluationRepositories,
) -> dict[str, tuple[UUID, ...]]:
    item_ids = await _finalized_item_ids(
        context=context, snapshot_id=snapshot_id, repositories=repositories
    )
    buckets = deterministic_split(item_ids, ratios=ratios, seed=seed)
    emit_audit_event(
        event="dataset_snapshot_split",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        snapshot_id=str(snapshot_id),
        buckets=sorted(buckets),
        population_size=len(item_ids),
    )
    return buckets
