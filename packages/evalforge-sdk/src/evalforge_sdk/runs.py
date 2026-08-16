"""Run ingestion models and client methods."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from evalforge_sdk.transport import EvalForgeTransport


@dataclass(frozen=True, slots=True)
class RunInput:
    workspace_id: UUID
    source: str
    started_at: datetime
    evaluation_target_id: UUID | None = None
    model_version_id: UUID | None = None
    prompt_version_id: UUID | None = None
    retrieval_config_version_id: UUID | None = None
    workflow_version_id: UUID | None = None
    pricing_version_id: UUID | None = None
    tool_definition_version_ids: tuple[UUID, ...] = ()
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "run-v1"

    def to_json(self) -> dict[str, Any]:
        return {
            "workspace_id": str(self.workspace_id),
            "evaluation_target_id": _opt_str(self.evaluation_target_id),
            "model_version_id": _opt_str(self.model_version_id),
            "prompt_version_id": _opt_str(self.prompt_version_id),
            "retrieval_config_version_id": _opt_str(self.retrieval_config_version_id),
            "workflow_version_id": _opt_str(self.workflow_version_id),
            "pricing_version_id": _opt_str(self.pricing_version_id),
            "tool_definition_version_ids": [str(i) for i in self.tool_definition_version_ids],
            "source": self.source,
            "correlation_id": self.correlation_id,
            "started_at": self.started_at.isoformat(),
            "metadata": self.metadata,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class RunFinalizeInput:
    status: str
    ended_at: datetime
    metadata: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ended_at": self.ended_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class RunRecord:
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    status: str
    source: str
    started_at: datetime
    ended_at: datetime | None
    metadata: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> RunRecord:
        return cls(
            id=UUID(data["id"]),
            tenant_id=UUID(data["tenant_id"]),
            workspace_id=UUID(data["workspace_id"]),
            status=data["status"],
            source=data["source"],
            started_at=datetime.fromisoformat(data["started_at"]),
            ended_at=_opt_datetime(data.get("ended_at")),
            metadata=data["metadata"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


def _opt_str(value: UUID | None) -> str | None:
    return str(value) if value is not None else None


def _opt_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class RunsClientMixin(EvalForgeTransport):
    async def create_run(
        self, *, tenant_id: UUID, run: RunInput, idempotency_key: str | None = None
    ) -> RunRecord:
        body = await self._request_json(
            "POST",
            f"/tenants/{tenant_id}/runs",
            json_body=run.to_json(),
            idempotency_key=idempotency_key or str(uuid4()),
        )
        return RunRecord.from_json(body)

    async def finalize_run(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        finalize: RunFinalizeInput,
        idempotency_key: str | None = None,
    ) -> RunRecord:
        body = await self._request_json(
            "POST",
            f"/tenants/{tenant_id}/runs/{run_id}/finalize",
            json_body=finalize.to_json(),
            idempotency_key=idempotency_key or str(uuid4()),
        )
        return RunRecord.from_json(body)

    async def get_run(self, *, tenant_id: UUID, run_id: UUID) -> RunRecord:
        body = await self._request_json("GET", f"/tenants/{tenant_id}/runs/{run_id}")
        return RunRecord.from_json(body)
