"""Artifact-upload ingestion endpoint.

Bytes and metadata are handled entirely through the reused Milestone 4
artifact boundary (``evalforge_api.application.artifact_service`` /
``artifact_ingestion_service``) — this module only parses the
multipart request, enforces the configured size ceiling, and
optionally attaches the resulting artifact version to a run or trace
as evidence in the same request.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from pydantic import BaseModel

from evalforge_api.application import artifact_ingestion_service, evidence_artifact_service
from evalforge_api.domain.hashing import hash_bytes
from evalforge_api.domain.ingestion import PayloadTooLargeError, compute_request_fingerprint
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.artifacts import ArtifactVersionRecord
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from evalforge_api.routes.ingestion_error_mapping import raise_as_http
from evalforge_api.security.dependencies import (
    get_db_pool,
    get_evaluation_repositories,
    get_ingestion_repositories,
    get_tenant_context,
)
from evalforge_api.settings import Settings, get_settings

router = APIRouter(prefix="/tenants/{tenant_id}/artifacts", tags=["ingestion"])

_IdempotencyKeyHeader = Header(..., alias="Idempotency-Key", min_length=1, max_length=200)
_MAX_PURPOSE_LENGTH = 200
_MAX_ROLE_LENGTH = 50


class ArtifactUploadResponse(BaseModel):
    artifact_id: UUID
    version_id: UUID
    version_number: int
    content_hash: str
    hash_algorithm: str
    byte_size: int
    content_type: str
    evidence_attached: bool

    @classmethod
    def from_records(
        cls, version: ArtifactVersionRecord, *, evidence_attached: bool
    ) -> ArtifactUploadResponse:
        return cls(
            artifact_id=version.artifact_id,
            version_id=version.id,
            version_number=version.version_number,
            content_hash=version.content_hash,
            hash_algorithm=version.hash_algorithm,
            byte_size=version.byte_size,
            content_type=version.content_type,
            evidence_attached=evidence_attached,
        )


async def _read_bounded(file: UploadFile, *, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLargeError(f"Artifact upload exceeds the {max_bytes}-byte limit.")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("", response_model=ArtifactUploadResponse)
async def post_upload_artifact(
    tenant_id: UUID,
    file: UploadFile = File(...),
    purpose: str = Form(..., min_length=1, max_length=_MAX_PURPOSE_LENGTH),
    workspace_id: UUID | None = Form(default=None),
    run_id: UUID | None = Form(default=None),
    trace_id: UUID | None = Form(default=None),
    role: str = Form(default="evidence", min_length=1, max_length=_MAX_ROLE_LENGTH),
    idempotency_key: str = _IdempotencyKeyHeader,
    context: TenantContext = Depends(get_tenant_context),
    evaluation_repositories: EvaluationRepositories = Depends(get_evaluation_repositories),
    ingestion_repositories: IngestionRepositories = Depends(get_ingestion_repositories),
    db_pool: asyncpg.Pool = Depends(get_db_pool),
    settings: Settings = Depends(get_settings),
) -> ArtifactUploadResponse:
    del tenant_id
    media_type = (file.content_type or "application/octet-stream")[:200]
    try:
        body = await _read_bounded(file, max_bytes=settings.max_artifact_bytes)
        upload_fingerprint = compute_request_fingerprint(
            {
                "purpose": purpose,
                "workspace_id": str(workspace_id) if workspace_id else None,
                "media_type": media_type,
                "content_hash": hash_bytes(body),
            }
        )
        version, created = await artifact_ingestion_service.upload_artifact(
            context=context,
            workspace_id=workspace_id,
            media_type=media_type,
            purpose=purpose,
            body=body,
            max_bytes=settings.max_artifact_bytes,
            idempotency_key=idempotency_key,
            request_fingerprint=upload_fingerprint,
            repositories=evaluation_repositories,
            db_pool=db_pool,
        )
        del created

        evidence_attached = False
        if run_id is not None or trace_id is not None:
            attach_fingerprint = compute_request_fingerprint(
                {
                    "artifact_version_id": str(version.id),
                    "role": role,
                    "run_id": str(run_id) if run_id else None,
                    "trace_id": str(trace_id) if trace_id else None,
                }
            )
            await evidence_artifact_service.attach_artifact(
                context=context,
                run_id=run_id,
                trace_id=trace_id,
                artifact_version_id=version.id,
                role=role,
                idempotency_key=idempotency_key,
                request_fingerprint=attach_fingerprint,
                evaluation_repositories=evaluation_repositories,
                ingestion_repositories=ingestion_repositories,
            )
            evidence_attached = True
    except Exception as exc:  # noqa: BLE001 -- translated by raise_as_http
        raise_as_http(exc)

    return ArtifactUploadResponse.from_records(version, evidence_attached=evidence_attached)
