"""EvalForge Python SDK — Milestone 5 run, trace, and artifact ingestion."""

from __future__ import annotations

from evalforge_sdk.artifacts import ArtifactUploadResult
from evalforge_sdk.client import EvalForgeClient
from evalforge_sdk.exceptions import (
    EvalForgeAPIError,
    EvalForgeConnectionError,
    EvalForgeSDKError,
    EvalForgeTimeoutError,
)
from evalforge_sdk.otel_mapping import otel_span_to_span_input
from evalforge_sdk.runs import RunFinalizeInput, RunInput, RunRecord
from evalforge_sdk.spans import SpanInput, SpanRecord
from evalforge_sdk.traces import TraceFinalizeInput, TraceInput, TraceRecord

__all__ = [
    "ArtifactUploadResult",
    "EvalForgeAPIError",
    "EvalForgeClient",
    "EvalForgeConnectionError",
    "EvalForgeSDKError",
    "EvalForgeTimeoutError",
    "RunFinalizeInput",
    "RunInput",
    "RunRecord",
    "SpanInput",
    "SpanRecord",
    "TraceFinalizeInput",
    "TraceInput",
    "TraceRecord",
    "otel_span_to_span_input",
]
