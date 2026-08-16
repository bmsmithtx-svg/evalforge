"""Span batch ingestion use cases.

Spans are ingested as a bounded batch under one idempotency key
(``evalforge_api.domain.ingestion.MAX_SPANS_PER_BATCH``). Every
optional model/retrieval/tool/workflow lineage reference and every
artifact reference is independently re-verified against the requesting
tenant before the batch is persisted.
"""

from __future__ import annotations

from uuid import UUID

from evalforge_api.adapters.span_repository import SpanInsertRejectedError
from evalforge_api.application.ingestion_validation import (
    validate_artifact_version,
    validate_resource_version,
)
from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.evaluation_enums import ResourceKind
from evalforge_api.domain.ingestion import (
    ImmutableTraceError,
    validate_attributes_size,
    validate_span_batch_size,
)
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from evalforge_api.ports.traces import SpanInput, SpanRecord

__all__ = [
    "AuthorizationDeniedError",
    "TraceNotFoundError",
    "ingest_spans",
    "list_spans",
]


class AuthorizationDeniedError(Exception):
    pass


class TraceNotFoundError(Exception):
    pass


_SPAN_RESOURCE_KIND_BY_FIELD: dict[str, ResourceKind] = {
    "model_version_id": ResourceKind.MODEL_CONFIG,
    "retrieval_config_version_id": ResourceKind.RETRIEVAL_CONFIG,
    "tool_definition_version_id": ResourceKind.TOOL_DEFINITION,
    "workflow_version_id": ResourceKind.WORKFLOW_DEFINITION,
}


async def _validate_span(
    *, tenant_id: UUID, span: SpanInput, evaluation_repositories: EvaluationRepositories
) -> None:
    validate_attributes_size(span.attributes)
    for field_name, expected_kind in _SPAN_RESOURCE_KIND_BY_FIELD.items():
        version_id = getattr(span, field_name)
        if version_id is None:
            continue
        await validate_resource_version(
            repositories=evaluation_repositories,
            tenant_id=tenant_id,
            version_id=version_id,
            expected_kind=expected_kind,
        )
    for artifact_field in ("input_artifact_version_id", "output_artifact_version_id"):
        artifact_version_id = getattr(span, artifact_field)
        if artifact_version_id is None:
            continue
        await validate_artifact_version(
            repositories=evaluation_repositories,
            tenant_id=tenant_id,
            version_id=artifact_version_id,
        )


async def ingest_spans(
    *,
    context: TenantContext,
    trace_id: UUID,
    spans: tuple[SpanInput, ...],
    idempotency_key: str,
    request_fingerprint: str,
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
) -> tuple[tuple[SpanRecord, ...], bool]:
    if not context.can(TenantAction.INGEST_TRACE):
        emit_audit_event(
            event="span_batch_ingestion",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to ingest spans.")

    validate_span_batch_size(len(spans))
    for span in spans:
        await _validate_span(
            tenant_id=context.tenant_id, span=span, evaluation_repositories=evaluation_repositories
        )

    trace = await ingestion_repositories.traces.get_trace(
        tenant_id=context.tenant_id, trace_id=trace_id
    )
    if trace is None:
        raise TraceNotFoundError(str(trace_id))
    # No pre-check against the trace's current status: the repository's
    # idempotency mechanism must run first so a genuine replay (same
    # key, same request) of a batch ingested before the trace was
    # finalized still returns the original result. A *new* batch
    # against a finalized trace still fails — the validate_span_insert
    # trigger enforces that independently (caught as
    # SpanInsertRejectedError below).
    try:
        records, created = await ingestion_repositories.spans.ingest_batch(
            tenant_id=context.tenant_id,
            trace_id=trace_id,
            spans=spans,
            created_by=context.user_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )
    except SpanInsertRejectedError as exc:
        emit_audit_event(
            event="span_batch_ingestion",
            outcome="denied_invalid",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            trace_id=str(trace_id),
        )
        raise ImmutableTraceError(str(exc)) from exc

    emit_audit_event(
        event="span_batch_ingestion",
        outcome="success" if created else "replayed",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        trace_id=str(trace_id),
        span_count=len(records),
    )
    return records, created


async def list_spans(
    *, context: TenantContext, trace_id: UUID, ingestion_repositories: IngestionRepositories
) -> tuple[SpanRecord, ...]:
    if not context.can(TenantAction.VIEW_TRACE):
        raise AuthorizationDeniedError("Not authorized to view this trace's spans.")
    trace = await ingestion_repositories.traces.get_trace(
        tenant_id=context.tenant_id, trace_id=trace_id
    )
    if trace is None:
        raise TraceNotFoundError(str(trace_id))
    return await ingestion_repositories.spans.list_for_trace(
        tenant_id=context.tenant_id, trace_id=trace_id
    )
