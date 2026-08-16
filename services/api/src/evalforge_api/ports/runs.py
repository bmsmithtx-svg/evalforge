"""Ports for run ingestion: captured execution-evidence persistence.

A run represents captured execution evidence submitted by an external
caller — Milestone 5 receives evidence, it does not execute or
schedule experiments (that is Milestone 7). Every optional reference
(evaluation target, model/prompt/retrieval/workflow/pricing version) is
an explicit relational lineage pointer, not opaque JSON
(docs/DOMAIN_MODEL.md), and every create/finalize operation is
idempotent — see ``evalforge_api.domain.ingestion``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from evalforge_api.domain.ingestion_enums import RunStatus


@dataclass(frozen=True, slots=True)
class RunRecord:
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    evaluation_target_id: UUID | None
    model_version_id: UUID | None
    prompt_version_id: UUID | None
    retrieval_config_version_id: UUID | None
    workflow_version_id: UUID | None
    pricing_version_id: UUID | None
    status: RunStatus
    source: str
    correlation_id: str | None
    started_at: datetime
    ended_at: datetime | None
    metadata: dict[str, Any]
    schema_version: str
    created_by: UUID
    created_at: datetime
    finalized_at: datetime | None


@dataclass(frozen=True, slots=True)
class RunToolVersionRecord:
    id: UUID
    tenant_id: UUID
    run_id: UUID
    tool_definition_version_id: UUID
    created_at: datetime


class RunRepository(Protocol):
    async def create_run(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        evaluation_target_id: UUID | None,
        model_version_id: UUID | None,
        prompt_version_id: UUID | None,
        retrieval_config_version_id: UUID | None,
        workflow_version_id: UUID | None,
        pricing_version_id: UUID | None,
        source: str,
        correlation_id: str | None,
        started_at: datetime,
        metadata: dict[str, Any],
        schema_version: str,
        created_by: UUID,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[RunRecord, bool]:
        """Returns the run and whether this call created it (``True``)
        or replayed an existing result for a repeated idempotency key
        (``False``)."""
        ...

    async def get_run(self, *, tenant_id: UUID, run_id: UUID) -> RunRecord | None: ...

    async def finalize_run(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        status: RunStatus,
        ended_at: datetime,
        metadata: dict[str, Any] | None,
        created_by: UUID,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[RunRecord, bool]: ...

    async def add_tool_version(
        self, *, tenant_id: UUID, run_id: UUID, tool_definition_version_id: UUID
    ) -> RunToolVersionRecord: ...

    async def list_tool_versions(
        self, *, tenant_id: UUID, run_id: UUID
    ) -> tuple[RunToolVersionRecord, ...]: ...
