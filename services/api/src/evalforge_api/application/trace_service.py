"""Trace ingestion use cases: create and finalize canonical traces.

A trace always belongs to exactly one run; its workspace is derived
from that run rather than accepted from the caller, so a request can
never attach a trace to a workspace inconsistent with its own run's
workspace (docs/TENANCY_AND_AUTHORIZATION.md — "tenant context must
never be trusted from arbitrary request payloads" extends naturally to
this kind of derived ownership).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from evalforge_api.adapters.trace_repository import TraceNotActiveError
from evalforge_api.adapters.trace_repository import TraceNotFoundError as _TraceRowNotFoundError
from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.ingestion import ImmutableTraceError, validate_metadata_size
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from evalforge_api.ports.traces import TraceRecord

__all__ = [
    "AuthorizationDeniedError",
    "RunNotFoundError",
    "TraceNotFoundError",
    "create_trace",
    "finalize_trace",
    "get_trace",
]


class AuthorizationDeniedError(Exception):
    pass


class RunNotFoundError(Exception):
    pass


class TraceNotFoundError(Exception):
    pass


async def create_trace(
    *,
    context: TenantContext,
    run_id: UUID,
    source: str,
    provider_trace_id: str | None,
    correlation_id: str | None,
    metadata: dict[str, Any],
    schema_version: str,
    idempotency_key: str,
    request_fingerprint: str,
    ingestion_repositories: IngestionRepositories,
) -> tuple[TraceRecord, bool]:
    if not context.can(TenantAction.INGEST_TRACE):
        emit_audit_event(
            event="trace_ingestion",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to ingest a trace.")

    validate_metadata_size(metadata)

    run = await ingestion_repositories.runs.get_run(tenant_id=context.tenant_id, run_id=run_id)
    if run is None:
        raise RunNotFoundError(str(run_id))

    trace, created = await ingestion_repositories.traces.create_trace(
        tenant_id=context.tenant_id,
        workspace_id=run.workspace_id,
        run_id=run_id,
        source=source,
        provider_trace_id=provider_trace_id,
        correlation_id=correlation_id,
        metadata=metadata,
        schema_version=schema_version,
        created_by=context.user_id,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )

    emit_audit_event(
        event="trace_ingestion",
        outcome="success" if created else "replayed",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        trace_id=str(trace.id),
        run_id=str(run_id),
    )
    return trace, created


async def get_trace(
    *, context: TenantContext, trace_id: UUID, ingestion_repositories: IngestionRepositories
) -> TraceRecord:
    if not context.can(TenantAction.VIEW_TRACE):
        raise AuthorizationDeniedError("Not authorized to view this trace.")
    trace = await ingestion_repositories.traces.get_trace(
        tenant_id=context.tenant_id, trace_id=trace_id
    )
    if trace is None:
        raise TraceNotFoundError(str(trace_id))
    return trace


async def finalize_trace(
    *,
    context: TenantContext,
    trace_id: UUID,
    started_at: datetime | None,
    ended_at: datetime | None,
    idempotency_key: str,
    request_fingerprint: str,
    ingestion_repositories: IngestionRepositories,
) -> tuple[TraceRecord, bool]:
    if not context.can(TenantAction.INGEST_TRACE):
        emit_audit_event(
            event="trace_finalization",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to finalize a trace.")

    # No pre-check against the trace's current status: the
    # repository's idempotency mechanism must run first so a genuine
    # replay (same key, same request) of an already-finalized trace
    # returns the original result rather than being rejected as
    # immutable. A *new* finalize attempt against a finalized trace
    # still fails — the forbid_finalized_trace_mutation trigger
    # enforces that independently of this service.
    try:
        trace, created = await ingestion_repositories.traces.finalize_trace(
            tenant_id=context.tenant_id,
            trace_id=trace_id,
            started_at=started_at,
            ended_at=ended_at,
            created_by=context.user_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )
    except _TraceRowNotFoundError as exc:
        raise TraceNotFoundError(str(trace_id)) from exc
    except TraceNotActiveError as exc:
        emit_audit_event(
            event="trace_finalization",
            outcome="denied_immutable",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            trace_id=str(trace_id),
        )
        raise ImmutableTraceError(f"Trace {trace_id} is no longer accepting changes.") from exc

    emit_audit_event(
        event="trace_finalization",
        outcome="success" if created else "replayed",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        trace_id=str(trace.id),
    )
    return trace, created
