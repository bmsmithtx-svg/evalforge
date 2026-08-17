"""Dataset authoring and lifecycle use cases.

A dataset is the mutable container; its *evidence* — versioned
test-case content and finalized snapshots — is immutable and lives
elsewhere. So this module is the one place in the dataset aggregate
that issues genuine updates, and every one of them is authorized and
audited.

Test-case authoring lives in
``evalforge_api.application.test_case_service``; ``create_test_case``
and ``create_test_case_version`` are re-exported here because they are
part of the same dataset-authoring vocabulary and were introduced at
this import path in Milestone 4.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from evalforge_api.application.dataset_errors import (
    AuthorizationDeniedError,
    DatasetNotFoundError,
    TestCaseNotFoundError,
)
from evalforge_api.application.test_case_service import (
    create_test_case,
    create_test_case_version,
)
from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.evaluation_enums import DatasetStatus
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.datasets import DatasetRecord
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories

__all__ = [
    "AuthorizationDeniedError",
    "DatasetNotFoundError",
    "TestCaseNotFoundError",
    "archive_dataset",
    "create_dataset",
    "create_test_case",
    "create_test_case_version",
    "get_dataset",
    "list_datasets",
    "update_dataset",
]


def _deny(event: str, context: TenantContext, message: str) -> None:
    emit_audit_event(
        event=event,
        outcome="denied",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        role=context.role.value,
    )
    raise AuthorizationDeniedError(message)


async def create_dataset(
    *,
    context: TenantContext,
    workspace_id: UUID,
    name: str,
    repositories: EvaluationRepositories,
    description: str | None = None,
    tags: Sequence[str] = (),
    metadata: dict[str, Any] | None = None,
) -> DatasetRecord:
    if not context.can(TenantAction.CREATE_DATASET):
        _deny("dataset_creation", context, "Not authorized to create a dataset.")

    dataset = await repositories.datasets.create_dataset(
        tenant_id=context.tenant_id,
        workspace_id=workspace_id,
        name=name,
        description=description,
        tags=tuple(tags),
        metadata=metadata or {},
        source="manual",
        cloned_from_dataset_id=None,
        cloned_from_snapshot_id=None,
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


async def get_dataset(
    *, context: TenantContext, dataset_id: UUID, repositories: EvaluationRepositories
) -> DatasetRecord:
    if not context.can(TenantAction.VIEW_DATASET):
        raise AuthorizationDeniedError("Not authorized to view this dataset.")
    dataset = await repositories.datasets.get_dataset(
        tenant_id=context.tenant_id, dataset_id=dataset_id
    )
    if dataset is None:
        raise DatasetNotFoundError(str(dataset_id))
    return dataset


async def list_datasets(
    *,
    context: TenantContext,
    repositories: EvaluationRepositories,
    workspace_id: UUID | None = None,
    status: DatasetStatus | None = None,
) -> tuple[DatasetRecord, ...]:
    if not context.can(TenantAction.VIEW_DATASET):
        raise AuthorizationDeniedError("Not authorized to view datasets.")
    return await repositories.datasets.list_datasets(
        tenant_id=context.tenant_id, workspace_id=workspace_id, status=status
    )


async def update_dataset(
    *,
    context: TenantContext,
    dataset_id: UUID,
    repositories: EvaluationRepositories,
    name: str | None = None,
    description: str | None = None,
    tags: Sequence[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> DatasetRecord:
    """Update a dataset's mutable metadata. Any argument left ``None``
    is untouched; this never reaches versioned content."""
    if not context.can(TenantAction.UPDATE_DATASET):
        _deny("dataset_update", context, "Not authorized to update a dataset.")

    updated = await repositories.datasets.update_dataset(
        tenant_id=context.tenant_id,
        dataset_id=dataset_id,
        name=name,
        description=description,
        tags=tuple(tags) if tags is not None else None,
        metadata=metadata,
        updated_by=context.user_id,
    )
    if updated is None:
        raise DatasetNotFoundError(str(dataset_id))
    emit_audit_event(
        event="dataset_update",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        dataset_id=str(dataset_id),
        changed_fields=sorted(
            field
            for field, value in (
                ("name", name),
                ("description", description),
                ("tags", tags),
                ("metadata", metadata),
            )
            if value is not None
        ),
    )
    return updated


async def archive_dataset(
    *, context: TenantContext, dataset_id: UUID, repositories: EvaluationRepositories
) -> DatasetRecord:
    """Archive a dataset. Archival is a status change, never a delete:
    finalized snapshots and versioned content remain readable so runs
    that referenced them stay explainable
    (docs/REPRODUCIBILITY_CONTRACT.md)."""
    if not context.can(TenantAction.ARCHIVE_DATASET):
        _deny("dataset_archival", context, "Not authorized to archive a dataset.")

    archived = await repositories.datasets.archive_dataset(
        tenant_id=context.tenant_id, dataset_id=dataset_id, updated_by=context.user_id
    )
    if archived is None:
        raise DatasetNotFoundError(str(dataset_id))
    emit_audit_event(
        event="dataset_archival",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        dataset_id=str(dataset_id),
    )
    return archived
