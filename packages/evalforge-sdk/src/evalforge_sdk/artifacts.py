"""Artifact upload models and client methods."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from evalforge_sdk.transport import EvalForgeTransport


@dataclass(frozen=True, slots=True)
class ArtifactUploadResult:
    artifact_id: UUID
    version_id: UUID
    version_number: int
    content_hash: str
    hash_algorithm: str
    byte_size: int
    content_type: str
    evidence_attached: bool

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ArtifactUploadResult:
        return cls(
            artifact_id=UUID(data["artifact_id"]),
            version_id=UUID(data["version_id"]),
            version_number=data["version_number"],
            content_hash=data["content_hash"],
            hash_algorithm=data["hash_algorithm"],
            byte_size=data["byte_size"],
            content_type=data["content_type"],
            evidence_attached=data["evidence_attached"],
        )


class ArtifactsClientMixin(EvalForgeTransport):
    async def upload_artifact(
        self,
        *,
        tenant_id: UUID,
        content: bytes,
        content_type: str,
        purpose: str,
        filename: str = "artifact",
        workspace_id: UUID | None = None,
        run_id: UUID | None = None,
        trace_id: UUID | None = None,
        role: str = "evidence",
        idempotency_key: str | None = None,
    ) -> ArtifactUploadResult:
        data: dict[str, Any] = {"purpose": purpose, "role": role}
        if workspace_id is not None:
            data["workspace_id"] = str(workspace_id)
        if run_id is not None:
            data["run_id"] = str(run_id)
        if trace_id is not None:
            data["trace_id"] = str(trace_id)

        response = await self._send(
            "POST",
            f"/tenants/{tenant_id}/artifacts",
            data=data,
            files={"file": (filename, content, content_type)},
            idempotency_key=idempotency_key or str(uuid4()),
        )
        result: dict[str, Any] = response.json()
        return ArtifactUploadResult.from_json(result)
