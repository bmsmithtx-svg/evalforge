"""Bulk import of test cases into an existing dataset.

All-or-nothing, deliberately
-----------------------------
Every record is validated first, purely, with no database access
(``evalforge_api.domain.import_parsing``). If *any* record fails
validation the entire import is rejected: nothing is written, and the
caller receives a per-record pass/fail report naming the exact row and
reason. Only when every record validates are the inserts performed,
inside a single database transaction.

The alternative — committing the valid rows and reporting the rest —
was rejected because a dataset that silently absorbed 97 of 100 rows
is a dataset whose contents nobody can state without re-reading the
import report. A rejected import leaves the dataset provably unchanged,
which is the property that makes retrying safe.

Every test case created by one call shares a single ``import_batch_id``
and is marked ``source = 'imported'``, so an import is identifiable and
reviewable after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from evalforge_api.application.dataset_errors import (
    AuthorizationDeniedError,
    DatasetNotFoundError,
)
from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.duplicate_detection import compute_dedup_hash
from evalforge_api.domain.hashing import (
    CANONICALIZATION_VERSION,
    HASH_ALGORITHM,
    hash_canonical_content,
)
from evalforge_api.domain.import_parsing import ParsedImportRow, parse_csv, parse_jsonl
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.datasets import TestCaseSeedRow
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories

IMPORT_FORMATS = ("csv", "jsonl")


class UnsupportedImportFormatError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ImportRecordResult:
    row_index: int
    success: bool
    test_case_id: UUID | None
    error: str | None


@dataclass(frozen=True, slots=True)
class ImportOutcome:
    records: tuple[ImportRecordResult, ...]
    committed: bool
    import_batch_id: UUID | None


def _parse(document: str, *, import_format: str) -> tuple[ParsedImportRow, ...]:
    if import_format == "csv":
        return parse_csv(document)
    if import_format == "jsonl":
        return parse_jsonl(document)
    raise UnsupportedImportFormatError(
        f"Unsupported import format {import_format!r}; expected one of {IMPORT_FORMATS}."
    )


async def import_test_cases(
    *,
    context: TenantContext,
    dataset_id: UUID,
    document: str,
    import_format: str,
    repositories: EvaluationRepositories,
) -> ImportOutcome:
    if not context.can(TenantAction.IMPORT_TEST_CASES):
        emit_audit_event(
            event="test_case_import",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to import test cases.")

    # Tenant-scoped: a dataset owned by another tenant is not found,
    # so an import can never target one.
    dataset = await repositories.datasets.get_dataset(
        tenant_id=context.tenant_id, dataset_id=dataset_id
    )
    if dataset is None:
        raise DatasetNotFoundError(str(dataset_id))

    parsed = _parse(document, import_format=import_format)
    failures = tuple(row for row in parsed if row.error is not None)
    if not parsed or failures:
        records = tuple(
            ImportRecordResult(
                row_index=row.row_index,
                success=row.error is None,
                test_case_id=None,
                error=row.error,
            )
            for row in parsed
        )
        emit_audit_event(
            event="test_case_import",
            outcome="rejected",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            dataset_id=str(dataset_id),
            record_count=len(parsed),
            failed_record_count=len(failures),
        )
        return ImportOutcome(records=records, committed=False, import_batch_id=None)

    import_batch_id = uuid4()
    seeds = []
    for row in parsed:
        assert row.content is not None  # every row validated above
        content = row.content.to_json_dict()
        seeds.append(
            TestCaseSeedRow(
                external_key=row.external_key,
                content=content,
                content_hash=hash_canonical_content(content),
                dedup_hash=compute_dedup_hash(row.content),
                source_test_case_id=None,
            )
        )

    versions = await repositories.datasets.create_test_cases_with_versions(
        tenant_id=context.tenant_id,
        dataset_id=dataset_id,
        rows=seeds,
        source="imported",
        import_batch_id=import_batch_id,
        hash_algorithm=HASH_ALGORITHM,
        canonicalization_version=CANONICALIZATION_VERSION,
        created_by=context.user_id,
    )
    records = tuple(
        ImportRecordResult(
            row_index=row.row_index,
            success=True,
            test_case_id=version.test_case_id,
            error=None,
        )
        for row, version in zip(parsed, versions, strict=True)
    )
    emit_audit_event(
        event="test_case_import",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        dataset_id=str(dataset_id),
        import_batch_id=str(import_batch_id),
        record_count=len(records),
    )
    return ImportOutcome(records=records, committed=True, import_batch_id=import_batch_id)
