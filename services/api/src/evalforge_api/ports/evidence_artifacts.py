"""Ports for attaching Milestone 4 artifact versions to ingested run
and trace evidence.

This is a pure linkage table: artifact bytes and metadata continue to
live entirely behind ``evalforge_api.ports.artifacts`` /
``evalforge_api.application.artifact_service`` (Milestone 4). Nothing
here duplicates or bypasses that boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EvidenceArtifactRecord:
    id: UUID
    tenant_id: UUID
    run_id: UUID | None
    trace_id: UUID | None
    artifact_version_id: UUID
    role: str
    created_at: datetime


class EvidenceArtifactRepository(Protocol):
    async def attach(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID | None,
        trace_id: UUID | None,
        artifact_version_id: UUID,
        role: str,
        created_by: UUID,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[EvidenceArtifactRecord, bool]: ...

    async def list_for_run(
        self, *, tenant_id: UUID, run_id: UUID
    ) -> tuple[EvidenceArtifactRecord, ...]: ...

    async def list_for_trace(
        self, *, tenant_id: UUID, trace_id: UUID
    ) -> tuple[EvidenceArtifactRecord, ...]: ...
