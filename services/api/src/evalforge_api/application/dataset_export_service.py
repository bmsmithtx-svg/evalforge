"""Export a dataset's test cases as CSV or JSONL.

Two sources, one format
-----------------------
Exporting a *finalized snapshot* is the preferred path: its membership
is immutable and identified by a content hash, so the export is
verifiable and reproducible. Exporting a dataset with no snapshot given
falls back to the current latest version of every active test case —
useful, but a moving target, which is why the emitted provenance header
records ``snapshot_id: null`` rather than pretending otherwise.

Ordering is deterministic in both cases: snapshot ``sequence_index``
for a snapshot export, test-case ID order otherwise. Rendering is pure
(``evalforge_api.domain.export_formatting``), which is also where the
provenance convention is documented.

Read-only: ``VIEW_DATASET_SNAPSHOT`` for a snapshot export,
``VIEW_DATASET`` for a current-state export.
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
from evalforge_api.domain.export_formatting import (
    ExportProvenance,
    ExportRow,
    format_csv,
    format_jsonl,
)
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.domain.test_case_content import TestCaseContent
from evalforge_api.ports.datasets import TestCaseVersionRecord
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories

EXPORT_FORMATS = ("csv", "jsonl")


class UnsupportedExportFormatError(Exception):
    pass


async def _export_row(
    *,
    context: TenantContext,
    version: TestCaseVersionRecord,
    sequence_index: int | None,
    repositories: EvaluationRepositories,
) -> ExportRow:
    test_case = await repositories.datasets.get_test_case(
        tenant_id=context.tenant_id, test_case_id=version.test_case_id
    )
    assert test_case is not None  # guaranteed by the composite tenant FK
    return ExportRow(
        test_case_id=version.test_case_id,
        external_key=test_case.external_key,
        version_id=version.id,
        version_number=version.version_number,
        content_hash=version.content_hash,
        sequence_index=sequence_index,
        content=TestCaseContent.from_json_dict(version.content),
    )


async def _snapshot_rows(
    *, context: TenantContext, snapshot_id: UUID, repositories: EvaluationRepositories
) -> tuple[tuple[ExportRow, ...], ExportProvenance]:
    snapshot = await repositories.snapshots.get_snapshot(
        tenant_id=context.tenant_id, snapshot_id=snapshot_id
    )
    if snapshot is None:
        raise SnapshotNotFoundError(str(snapshot_id))

    items = await repositories.snapshots.list_items(
        tenant_id=context.tenant_id, snapshot_id=snapshot_id
    )
    rows: list[ExportRow] = []
    for item in items:
        version = await repositories.datasets.get_test_case_version(
            tenant_id=context.tenant_id, version_id=item.test_case_version_id
        )
        assert version is not None  # guaranteed by the composite tenant FK
        rows.append(
            await _export_row(
                context=context,
                version=version,
                sequence_index=item.sequence_index,
                repositories=repositories,
            )
        )
    provenance = ExportProvenance(
        dataset_id=snapshot.dataset_id,
        snapshot_id=snapshot.id,
        snapshot_content_hash=snapshot.content_hash,
    )
    return tuple(rows), provenance


async def _current_rows(
    *, context: TenantContext, dataset_id: UUID, repositories: EvaluationRepositories
) -> tuple[tuple[ExportRow, ...], ExportProvenance]:
    dataset = await repositories.datasets.get_dataset(
        tenant_id=context.tenant_id, dataset_id=dataset_id
    )
    if dataset is None:
        raise DatasetNotFoundError(str(dataset_id))

    versions = await repositories.datasets.list_latest_versions_for_dataset(
        tenant_id=context.tenant_id, dataset_id=dataset_id
    )
    rows = [
        await _export_row(
            context=context, version=version, sequence_index=None, repositories=repositories
        )
        for version in versions
    ]
    provenance = ExportProvenance(
        dataset_id=dataset_id, snapshot_id=None, snapshot_content_hash=None
    )
    return tuple(rows), provenance


async def export_dataset(
    *,
    context: TenantContext,
    dataset_id: UUID,
    snapshot_id: UUID | None,
    export_format: str,
    repositories: EvaluationRepositories,
) -> str:
    required = (
        TenantAction.VIEW_DATASET_SNAPSHOT if snapshot_id is not None else TenantAction.VIEW_DATASET
    )
    if not context.can(required):
        emit_audit_event(
            event="dataset_export",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to export this dataset.")
    if export_format not in EXPORT_FORMATS:
        raise UnsupportedExportFormatError(
            f"Unsupported export format {export_format!r}; expected one of {EXPORT_FORMATS}."
        )

    if snapshot_id is not None:
        rows, provenance = await _snapshot_rows(
            context=context, snapshot_id=snapshot_id, repositories=repositories
        )
        if provenance.dataset_id != dataset_id:
            raise SnapshotNotFoundError(str(snapshot_id))
    else:
        rows, provenance = await _current_rows(
            context=context, dataset_id=dataset_id, repositories=repositories
        )

    document = (
        format_jsonl(rows, provenance=provenance)
        if export_format == "jsonl"
        else format_csv(rows, provenance=provenance)
    )
    emit_audit_event(
        event="dataset_export",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        dataset_id=str(dataset_id),
        snapshot_id=str(snapshot_id) if snapshot_id else None,
        export_format=export_format,
        record_count=len(rows),
    )
    return document
