"""Optional OpenTelemetry-shaped span mapping.

Translates a provider-neutral OpenTelemetry-like span dictionary (the
common shape exported by OTel-compatible SDKs and collectors — trace
id, span id, parent span id, name, start/end time, status, attributes)
into an EvalForge ``SpanInput``. This is a pure mapping function behind
the interoperability boundary described in docs/ARCHITECTURE.md; it
does not depend on the ``opentelemetry-sdk`` package or any vendor's
span object, only on plain dict/duck-typed input, so EvalForge's
canonical domain never couples to one vendor's schema.

EvalForge's ``span_kind`` (llm_call / retrieval_call / tool_call /
workflow_step / other) is semantic classification of what a span
*represents*, which OpenTelemetry's own ``SpanKind``
(CLIENT/SERVER/INTERNAL/PRODUCER/CONSUMER) does not carry — callers
supply it explicitly rather than have this mapper guess.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from evalforge_sdk.spans import SpanInput

_OTEL_OK_STATUS_CODES = {"OK", "UNSET"}


def _epoch_nanos_to_datetime(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1_000_000_000, tz=UTC)


def otel_span_to_span_input(otel_span: dict[str, Any], *, span_kind: str = "other") -> SpanInput:
    """Map one OpenTelemetry-shaped span dict to a ``SpanInput``.

    ``otel_span`` is expected to carry (at minimum) ``span_id``,
    ``name``, and ``start_time_unix_nano``, and optionally
    ``parent_span_id``, ``end_time_unix_nano``, ``status``
    (``{"code": ..., "message": ...}``), and ``attributes``.
    """
    status = otel_span.get("status") or {}
    status_code = str(status.get("code", "OK")).upper()
    end_time = otel_span.get("end_time_unix_nano")
    parent_span_id = otel_span.get("parent_span_id")

    return SpanInput(
        span_id=str(otel_span["span_id"]),
        parent_span_id=str(parent_span_id) if parent_span_id else None,
        name=str(otel_span.get("name", "unknown")),
        span_kind=span_kind,
        status="ok" if status_code in _OTEL_OK_STATUS_CODES else "error",
        error_message=status.get("message"),
        started_at=_epoch_nanos_to_datetime(int(otel_span["start_time_unix_nano"])),
        ended_at=_epoch_nanos_to_datetime(int(end_time)) if end_time else None,
        attributes=dict(otel_span.get("attributes", {})),
    )
