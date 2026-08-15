"""Ports for versioned evaluation-configuration resources.

Covers the seven versioned concepts fixed by the domain model — model,
prompt, retrieval, tool, workflow, evaluator, and pricing versions —
which share identical versioning mechanics and differ only by
``ResourceKind`` and the JSON shape of ``content``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from evalforge_api.domain.evaluation_enums import (
    ResourceKind,
    RetentionClass,
    VersionedResourceStatus,
)


@dataclass(frozen=True, slots=True)
class VersionedResourceRecord:
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    kind: ResourceKind
    name: str
    status: VersionedResourceStatus
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class VersionedResourceVersionRecord:
    id: UUID
    tenant_id: UUID
    resource_id: UUID
    version_number: int
    content: dict[str, Any]
    content_hash: str
    hash_algorithm: str
    canonicalization_version: str
    derived_from_version_id: UUID | None
    retention_class: RetentionClass
    retain_until: datetime | None
    archived_at: datetime | None
    created_by: UUID
    created_at: datetime


class VersionedResourceRepository(Protocol):
    async def create_resource(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        kind: ResourceKind,
        name: str,
        created_by: UUID,
    ) -> VersionedResourceRecord: ...

    async def get_resource(
        self, *, tenant_id: UUID, resource_id: UUID
    ) -> VersionedResourceRecord | None: ...

    async def create_version(
        self,
        *,
        tenant_id: UUID,
        resource_id: UUID,
        version_number: int,
        content: dict[str, Any],
        content_hash: str,
        hash_algorithm: str,
        canonicalization_version: str,
        derived_from_version_id: UUID | None,
        created_by: UUID,
    ) -> VersionedResourceVersionRecord: ...

    async def get_version(
        self, *, tenant_id: UUID, version_id: UUID
    ) -> VersionedResourceVersionRecord | None: ...

    async def list_versions(
        self, *, tenant_id: UUID, resource_id: UUID
    ) -> tuple[VersionedResourceVersionRecord, ...]: ...
