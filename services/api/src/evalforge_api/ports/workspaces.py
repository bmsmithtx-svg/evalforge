"""Ports for workspace and evaluation-target persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from evalforge_api.domain.evaluation_enums import EvaluationTargetStatus, WorkspaceStatus


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    id: UUID
    tenant_id: UUID
    slug: str
    name: str
    status: WorkspaceStatus
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EvaluationTargetRecord:
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    name: str
    target_type: str
    status: EvaluationTargetStatus
    created_by: UUID
    created_at: datetime


class WorkspaceRepository(Protocol):
    async def create(
        self, *, tenant_id: UUID, slug: str, name: str, created_by: UUID
    ) -> WorkspaceRecord: ...

    async def get_by_id(self, *, tenant_id: UUID, workspace_id: UUID) -> WorkspaceRecord | None: ...

    async def list_for_tenant(self, *, tenant_id: UUID) -> tuple[WorkspaceRecord, ...]: ...


class EvaluationTargetRepository(Protocol):
    async def create(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        name: str,
        target_type: str,
        created_by: UUID,
    ) -> EvaluationTargetRecord: ...

    async def get_by_id(
        self, *, tenant_id: UUID, target_id: UUID
    ) -> EvaluationTargetRecord | None: ...

    async def list_for_workspace(
        self, *, tenant_id: UUID, workspace_id: UUID
    ) -> tuple[EvaluationTargetRecord, ...]: ...
