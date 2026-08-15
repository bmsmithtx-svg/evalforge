"""Ports for artifact metadata persistence and object-storage bytes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from evalforge_api.domain.evaluation_enums import ArtifactStatus, RetentionClass


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    id: UUID
    tenant_id: UUID
    workspace_id: UUID | None
    media_type: str
    purpose: str
    status: ArtifactStatus
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ArtifactVersionRecord:
    id: UUID
    tenant_id: UUID
    artifact_id: UUID
    version_number: int
    content_hash: str
    hash_algorithm: str
    byte_size: int
    content_type: str
    storage_key: str
    derived_from_artifact_version_id: UUID | None
    retention_class: RetentionClass
    retain_until: datetime | None
    archived_at: datetime | None
    created_by: UUID
    created_at: datetime


class ArtifactRepository(Protocol):
    async def create_artifact(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID | None,
        media_type: str,
        purpose: str,
        created_by: UUID,
    ) -> ArtifactRecord: ...

    async def get_artifact(
        self, *, tenant_id: UUID, artifact_id: UUID
    ) -> ArtifactRecord | None: ...

    async def create_artifact_version(
        self,
        *,
        tenant_id: UUID,
        artifact_id: UUID,
        version_number: int,
        content_hash: str,
        hash_algorithm: str,
        byte_size: int,
        content_type: str,
        storage_key: str,
        derived_from_artifact_version_id: UUID | None,
        created_by: UUID,
    ) -> ArtifactVersionRecord: ...

    async def get_artifact_version(
        self, *, tenant_id: UUID, version_id: UUID
    ) -> ArtifactVersionRecord | None: ...

    async def list_artifact_versions(
        self, *, tenant_id: UUID, artifact_id: UUID
    ) -> tuple[ArtifactVersionRecord, ...]: ...


class ArtifactObjectStorage(Protocol):
    """Tenant-scoped object-storage bytes for artifact content.

    Callers pass a fully-qualified, tenant-scoped key (see
    ``evalforge_api.application.artifact_service`` for key
    construction) — this port never derives tenant scoping itself.
    """

    async def put_object(self, *, key: str, body: bytes, content_type: str) -> None: ...

    async def get_object(self, *, key: str) -> bytes: ...

    async def object_exists(self, *, key: str) -> bool: ...
