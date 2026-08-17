"""Dataset import and export endpoints.

Import accepts a multipart file upload, matching the Milestone 5
artifact-upload pattern (``routes/ingestion_artifacts``), and is
bounded by the same configured request-size ceiling before the bytes
are decoded. It is all-or-nothing: a rejected import returns HTTP 200
with ``committed = false`` and a per-row report, because the request
itself was well-formed and the report *is* the answer — an error
status would give the caller nothing to act on.

Export returns the raw CSV or JSONL document as a downloadable
response, with provenance embedded in the document itself (see
``evalforge_api.domain.export_formatting``).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from pydantic import BaseModel

from evalforge_api.application import dataset_export_service, dataset_import_service
from evalforge_api.domain.ingestion import PayloadTooLargeError
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.routes.dataset_error_mapping import raise_as_http
from evalforge_api.security.dependencies import get_evaluation_repositories, get_tenant_context
from evalforge_api.settings import Settings, get_settings

router = APIRouter(prefix="/tenants/{tenant_id}/datasets/{dataset_id}", tags=["datasets"])

_MEDIA_TYPE_BY_FORMAT = {"csv": "text/csv", "jsonl": "application/x-ndjson"}


class ImportRecordResultResponse(BaseModel):
    row_index: int
    success: bool
    test_case_id: UUID | None
    error: str | None


class ImportOutcomeResponse(BaseModel):
    dataset_id: UUID
    committed: bool
    import_batch_id: UUID | None
    record_count: int
    failed_record_count: int
    records: list[ImportRecordResultResponse]


async def _read_bounded_text(file: UploadFile, *, max_bytes: int) -> str:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLargeError(f"Import document exceeds the {max_bytes}-byte limit.")
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


@router.post("/import", response_model=ImportOutcomeResponse)
async def post_import_test_cases(
    tenant_id: UUID,
    dataset_id: UUID,
    file: UploadFile = File(...),
    import_format: str = Form(..., alias="format", min_length=1, max_length=10),
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
    settings: Settings = Depends(get_settings),
) -> ImportOutcomeResponse:
    del tenant_id  # resolved and verified by get_tenant_context
    try:
        document = await _read_bounded_text(file, max_bytes=settings.max_request_body_bytes)
        outcome = await dataset_import_service.import_test_cases(
            context=context,
            dataset_id=dataset_id,
            document=document,
            import_format=import_format.lower(),
            repositories=repositories,
        )
    except PayloadTooLargeError as exc:
        raise_as_http(exc)
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    return ImportOutcomeResponse(
        dataset_id=dataset_id,
        committed=outcome.committed,
        import_batch_id=outcome.import_batch_id,
        record_count=len(outcome.records),
        failed_record_count=sum(1 for record in outcome.records if not record.success),
        records=[
            ImportRecordResultResponse(
                row_index=record.row_index,
                success=record.success,
                test_case_id=record.test_case_id,
                error=record.error,
            )
            for record in outcome.records
        ],
    )


@router.get("/export")
async def get_export_dataset(
    tenant_id: UUID,
    dataset_id: UUID,
    export_format: str = Query(default="jsonl", alias="format", max_length=10),
    snapshot_id: UUID | None = Query(default=None),
    context: TenantContext = Depends(get_tenant_context),
    repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
) -> Response:
    del tenant_id
    normalized = export_format.lower()
    try:
        document = await dataset_export_service.export_dataset(
            context=context,
            dataset_id=dataset_id,
            snapshot_id=snapshot_id,
            export_format=normalized,
            repositories=repositories,
        )
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)
    suffix = snapshot_id or dataset_id
    return Response(
        content=document,
        media_type=_MEDIA_TYPE_BY_FORMAT.get(normalized, "text/plain"),
        headers={"Content-Disposition": f'attachment; filename="evalforge-{suffix}.{normalized}"'},
    )
