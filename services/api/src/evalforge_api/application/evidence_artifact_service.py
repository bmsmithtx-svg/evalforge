"""Evidence-artifact attachment use cases.

Attaches an existing Milestone 4 artifact version (created through
``evalforge_api.application.artifact_service``, which already enforces
artifact size limits, tenant-scoped storage keys, and hash
verification) to a run or trace as supporting evidence. This module
never touches artifact bytes; it only manages the linkage row and the
authorization/tenant checks around it, reusing the same
``TenantAction.CREATE_ARTIFACT`` permission Milestone 4 established
rather than inventing a parallel authorization concept.
"""

from __future__ import annotations

from uuid import UUID

from evalforge_api.application.ingestion_validation import validate_artifact_version
from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.evidence_artifacts import EvidenceArtifactRecord
from evalforge_api.ports.ingestion_repositories import IngestionRepositories

__all__ = [
    "AuthorizationDeniedError",
    "InvalidEvidenceOwnerError",
    "RunNotFoundError",
    "TraceNotFoundError",
    "attach_artifact",
]


class AuthorizationDeniedError(Exception):
    pass


class InvalidEvidenceOwnerError(Exception):
    pass


class RunNotFoundError(Exception):
    pass


class TraceNotFoundError(Exception):
    pass


async def attach_artifact(
    *,
    context: TenantContext,
    run_id: UUID | None,
    trace_id: UUID | None,
    artifact_version_id: UUID,
    role: str,
    idempotency_key: str,
    request_fingerprint: str,
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
) -> tuple[EvidenceArtifactRecord, bool]:
    if (run_id is None) == (trace_id is None):
        raise InvalidEvidenceOwnerError("Exactly one of run_id or trace_id must be provided.")

    if not context.can(TenantAction.CREATE_ARTIFACT):
        emit_audit_event(
            event="evidence_artifact_attachment",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to attach evidence artifacts.")

    await validate_artifact_version(
        repositories=evaluation_repositories,
        tenant_id=context.tenant_id,
        version_id=artifact_version_id,
    )

    if run_id is not None:
        run = await ingestion_repositories.runs.get_run(tenant_id=context.tenant_id, run_id=run_id)
        if run is None:
            raise RunNotFoundError(str(run_id))
    if trace_id is not None:
        trace = await ingestion_repositories.traces.get_trace(
            tenant_id=context.tenant_id, trace_id=trace_id
        )
        if trace is None:
            raise TraceNotFoundError(str(trace_id))

    record, created = await ingestion_repositories.evidence_artifacts.attach(
        tenant_id=context.tenant_id,
        run_id=run_id,
        trace_id=trace_id,
        artifact_version_id=artifact_version_id,
        role=role,
        created_by=context.user_id,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )

    emit_audit_event(
        event="evidence_artifact_attachment",
        outcome="success" if created else "replayed",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        run_id=str(run_id) if run_id else None,
        trace_id=str(trace_id) if trace_id else None,
        artifact_version_id=str(artifact_version_id),
    )
    return record, created
