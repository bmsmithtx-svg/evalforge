"""Run ingestion use cases: create and finalize captured execution
evidence.

A run represents externally produced execution evidence — Milestone 5
receives it, it does not execute or schedule experiments (Milestone
7). Every optional lineage reference is independently re-verified
against the requesting tenant before being persisted
(``evalforge_api.application.ingestion_validation``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from evalforge_api.adapters.run_repository import RunNotActiveError
from evalforge_api.adapters.run_repository import RunNotFoundError as _RunRowNotFoundError
from evalforge_api.application.ingestion_validation import (
    validate_evaluation_target,
    validate_resource_version,
    validate_workspace,
)
from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.evaluation_enums import ResourceKind
from evalforge_api.domain.ingestion import ImmutableRunError, validate_metadata_size
from evalforge_api.domain.ingestion_enums import RunStatus
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from evalforge_api.ports.runs import RunRecord

__all__ = [
    "AuthorizationDeniedError",
    "RunNotFoundError",
    "create_run",
    "finalize_run",
    "get_run",
]


class AuthorizationDeniedError(Exception):
    pass


class RunNotFoundError(Exception):
    pass


_RESOURCE_KIND_BY_FIELD: dict[str, ResourceKind] = {
    "model_version_id": ResourceKind.MODEL_CONFIG,
    "prompt_version_id": ResourceKind.PROMPT_CONFIG,
    "retrieval_config_version_id": ResourceKind.RETRIEVAL_CONFIG,
    "workflow_version_id": ResourceKind.WORKFLOW_DEFINITION,
    "pricing_version_id": ResourceKind.PRICING_ASSUMPTION,
}


async def _validate_lineage_references(
    *,
    tenant_id: UUID,
    workspace_id: UUID,
    evaluation_target_id: UUID | None,
    resource_version_ids: dict[str, UUID | None],
    tool_definition_version_ids: tuple[UUID, ...],
    evaluation_repositories: EvaluationRepositories,
) -> None:
    await validate_workspace(
        repositories=evaluation_repositories, tenant_id=tenant_id, workspace_id=workspace_id
    )
    if evaluation_target_id is not None:
        await validate_evaluation_target(
            repositories=evaluation_repositories,
            tenant_id=tenant_id,
            target_id=evaluation_target_id,
        )
    for field_name, version_id in resource_version_ids.items():
        if version_id is None:
            continue
        await validate_resource_version(
            repositories=evaluation_repositories,
            tenant_id=tenant_id,
            version_id=version_id,
            expected_kind=_RESOURCE_KIND_BY_FIELD[field_name],
        )
    for tool_version_id in tool_definition_version_ids:
        await validate_resource_version(
            repositories=evaluation_repositories,
            tenant_id=tenant_id,
            version_id=tool_version_id,
            expected_kind=ResourceKind.TOOL_DEFINITION,
        )


async def create_run(
    *,
    context: TenantContext,
    workspace_id: UUID,
    evaluation_target_id: UUID | None,
    model_version_id: UUID | None,
    prompt_version_id: UUID | None,
    retrieval_config_version_id: UUID | None,
    workflow_version_id: UUID | None,
    pricing_version_id: UUID | None,
    tool_definition_version_ids: tuple[UUID, ...],
    source: str,
    correlation_id: str | None,
    started_at: datetime,
    metadata: dict[str, Any],
    schema_version: str,
    idempotency_key: str,
    request_fingerprint: str,
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
) -> tuple[RunRecord, bool]:
    if not context.can(TenantAction.INGEST_RUN):
        emit_audit_event(
            event="run_ingestion",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to ingest a run.")

    validate_metadata_size(metadata)
    await _validate_lineage_references(
        tenant_id=context.tenant_id,
        workspace_id=workspace_id,
        evaluation_target_id=evaluation_target_id,
        resource_version_ids={
            "model_version_id": model_version_id,
            "prompt_version_id": prompt_version_id,
            "retrieval_config_version_id": retrieval_config_version_id,
            "workflow_version_id": workflow_version_id,
            "pricing_version_id": pricing_version_id,
        },
        tool_definition_version_ids=tool_definition_version_ids,
        evaluation_repositories=evaluation_repositories,
    )

    run, created = await ingestion_repositories.runs.create_run(
        tenant_id=context.tenant_id,
        workspace_id=workspace_id,
        evaluation_target_id=evaluation_target_id,
        model_version_id=model_version_id,
        prompt_version_id=prompt_version_id,
        retrieval_config_version_id=retrieval_config_version_id,
        workflow_version_id=workflow_version_id,
        pricing_version_id=pricing_version_id,
        source=source,
        correlation_id=correlation_id,
        started_at=started_at,
        metadata=metadata,
        schema_version=schema_version,
        created_by=context.user_id,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )

    if created:
        for tool_version_id in tool_definition_version_ids:
            await ingestion_repositories.runs.add_tool_version(
                tenant_id=context.tenant_id,
                run_id=run.id,
                tool_definition_version_id=tool_version_id,
            )

    emit_audit_event(
        event="run_ingestion",
        outcome="success" if created else "replayed",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        run_id=str(run.id),
    )
    return run, created


async def get_run(
    *, context: TenantContext, run_id: UUID, ingestion_repositories: IngestionRepositories
) -> RunRecord:
    if not context.can(TenantAction.VIEW_RUN):
        raise AuthorizationDeniedError("Not authorized to view this run.")
    run = await ingestion_repositories.runs.get_run(tenant_id=context.tenant_id, run_id=run_id)
    if run is None:
        raise RunNotFoundError(str(run_id))
    return run


async def finalize_run(
    *,
    context: TenantContext,
    run_id: UUID,
    status: RunStatus,
    ended_at: datetime,
    metadata: dict[str, Any] | None,
    idempotency_key: str,
    request_fingerprint: str,
    ingestion_repositories: IngestionRepositories,
) -> tuple[RunRecord, bool]:
    if not context.can(TenantAction.INGEST_RUN):
        emit_audit_event(
            event="run_finalization",
            outcome="denied",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            role=context.role.value,
        )
        raise AuthorizationDeniedError("Not authorized to finalize a run.")

    if metadata is not None:
        validate_metadata_size(metadata)

    # No pre-check against the run's current status here: the
    # repository's idempotency mechanism must run first so a genuine
    # replay (same key, same request) of an already-finalized run
    # returns the original result rather than being rejected as
    # immutable. A *new* finalize attempt against a terminal run still
    # fails — the forbid_terminal_run_mutation trigger enforces that
    # independently of this service.
    try:
        run, created = await ingestion_repositories.runs.finalize_run(
            tenant_id=context.tenant_id,
            run_id=run_id,
            status=status,
            ended_at=ended_at,
            metadata=metadata,
            created_by=context.user_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )
    except _RunRowNotFoundError as exc:
        raise RunNotFoundError(str(run_id)) from exc
    except RunNotActiveError as exc:
        emit_audit_event(
            event="run_finalization",
            outcome="denied_immutable",
            actor_user_id=str(context.user_id),
            tenant_id=str(context.tenant_id),
            run_id=str(run_id),
        )
        raise ImmutableRunError(f"Run {run_id} is no longer active.") from exc

    emit_audit_event(
        event="run_finalization",
        outcome="success" if created else "replayed",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        run_id=str(run.id),
        status=status.value,
    )
    return run, created
