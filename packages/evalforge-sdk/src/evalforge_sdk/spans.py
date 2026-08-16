"""Span batch ingestion models and client methods."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from evalforge_sdk.transport import EvalForgeTransport


@dataclass(frozen=True, slots=True)
class SpanInput:
    span_id: str
    name: str
    span_kind: str
    started_at: datetime
    parent_span_id: str | None = None
    status: str = "ok"
    error_message: str | None = None
    ended_at: datetime | None = None
    model_version_id: UUID | None = None
    retrieval_config_version_id: UUID | None = None
    tool_definition_version_id: UUID | None = None
    workflow_version_id: UUID | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    input_artifact_version_id: UUID | None = None
    output_artifact_version_id: UUID | None = None
    token_count_input: int | None = None
    token_count_output: int | None = None
    cost_amount: Decimal | None = None
    cost_currency: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "span_kind": self.span_kind,
            "status": self.status,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "model_version_id": _opt_str(self.model_version_id),
            "retrieval_config_version_id": _opt_str(self.retrieval_config_version_id),
            "tool_definition_version_id": _opt_str(self.tool_definition_version_id),
            "workflow_version_id": _opt_str(self.workflow_version_id),
            "attributes": self.attributes,
            "input_artifact_version_id": _opt_str(self.input_artifact_version_id),
            "output_artifact_version_id": _opt_str(self.output_artifact_version_id),
            "token_count_input": self.token_count_input,
            "token_count_output": self.token_count_output,
            "cost_amount": str(self.cost_amount) if self.cost_amount is not None else None,
            "cost_currency": self.cost_currency,
        }


@dataclass(frozen=True, slots=True)
class SpanRecord:
    id: UUID
    trace_id: UUID
    parent_span_id: UUID | None
    provider_span_id: str | None
    name: str
    span_kind: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    attributes: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> SpanRecord:
        return cls(
            id=UUID(data["id"]),
            trace_id=UUID(data["trace_id"]),
            parent_span_id=UUID(data["parent_span_id"]) if data.get("parent_span_id") else None,
            provider_span_id=data.get("provider_span_id"),
            name=data["name"],
            span_kind=data["span_kind"],
            status=data["status"],
            started_at=datetime.fromisoformat(data["started_at"]),
            ended_at=datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None,
            attributes=data["attributes"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


def _opt_str(value: UUID | None) -> str | None:
    return str(value) if value is not None else None


class SpansClientMixin(EvalForgeTransport):
    async def ingest_spans(
        self,
        *,
        tenant_id: UUID,
        trace_id: UUID,
        spans: tuple[SpanInput, ...],
        idempotency_key: str | None = None,
    ) -> tuple[SpanRecord, ...]:
        body = await self._request_json_list(
            "POST",
            f"/tenants/{tenant_id}/traces/{trace_id}/spans",
            json_body={"spans": [span.to_json() for span in spans]},
            idempotency_key=idempotency_key or str(uuid4()),
        )
        return tuple(SpanRecord.from_json(item) for item in body)

    async def list_spans(self, *, tenant_id: UUID, trace_id: UUID) -> tuple[SpanRecord, ...]:
        body = await self._request_json_list("GET", f"/tenants/{tenant_id}/traces/{trace_id}/spans")
        return tuple(SpanRecord.from_json(item) for item in body)
