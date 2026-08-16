"""Trace ingestion models and client methods.

Span-batch ingestion lives in ``evalforge_sdk.spans``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from evalforge_sdk.transport import EvalForgeTransport


@dataclass(frozen=True, slots=True)
class TraceInput:
    run_id: UUID
    source: str
    provider_trace_id: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "trace-v1"

    def to_json(self) -> dict[str, Any]:
        return {
            "run_id": str(self.run_id),
            "source": self.source,
            "provider_trace_id": self.provider_trace_id,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class TraceFinalizeInput:
    started_at: datetime | None = None
    ended_at: datetime | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }


@dataclass(frozen=True, slots=True)
class TraceRecord:
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    run_id: UUID
    status: str
    source: str
    metadata: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> TraceRecord:
        return cls(
            id=UUID(data["id"]),
            tenant_id=UUID(data["tenant_id"]),
            workspace_id=UUID(data["workspace_id"]),
            run_id=UUID(data["run_id"]),
            status=data["status"],
            source=data["source"],
            metadata=data["metadata"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class TracesClientMixin(EvalForgeTransport):
    async def create_trace(
        self, *, tenant_id: UUID, trace: TraceInput, idempotency_key: str | None = None
    ) -> TraceRecord:
        body = await self._request_json(
            "POST",
            f"/tenants/{tenant_id}/traces",
            json_body=trace.to_json(),
            idempotency_key=idempotency_key or str(uuid4()),
        )
        return TraceRecord.from_json(body)

    async def finalize_trace(
        self,
        *,
        tenant_id: UUID,
        trace_id: UUID,
        finalize: TraceFinalizeInput,
        idempotency_key: str | None = None,
    ) -> TraceRecord:
        body = await self._request_json(
            "POST",
            f"/tenants/{tenant_id}/traces/{trace_id}/finalize",
            json_body=finalize.to_json(),
            idempotency_key=idempotency_key or str(uuid4()),
        )
        return TraceRecord.from_json(body)

    async def get_trace(self, *, tenant_id: UUID, trace_id: UUID) -> TraceRecord:
        body = await self._request_json("GET", f"/tenants/{tenant_id}/traces/{trace_id}")
        return TraceRecord.from_json(body)
