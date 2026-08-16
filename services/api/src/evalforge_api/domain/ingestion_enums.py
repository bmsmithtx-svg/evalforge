"""Milestone 5 ingestion-domain enums.

These mirror the Postgres enum types created by the ingestion
migrations. Kept separate from ``domain/evaluation_enums.py`` because
they describe a distinct set of concepts (execution evidence rather
than versioned configuration).
"""

from __future__ import annotations

from enum import StrEnum


class RunStatus(StrEnum):
    """Run lifecycle, restricted to what Milestone 5 ingestion needs.

    ``queued`` is omitted: Milestone 5 receives evidence produced by an
    external execution, it does not schedule execution itself (that is
    Milestone 7). ``RUNNING`` is the only non-terminal state; once a
    run reaches a terminal state it is immutable (see
    ``ensure_run_is_active`` below).
    """

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


TERMINAL_RUN_STATUSES = frozenset({RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELED})


class TraceStatus(StrEnum):
    """Trace lifecycle: appendable while ``INGESTING``, immutable once
    ``FINALIZED`` (docs/DOMAIN_MODEL.md)."""

    INGESTING = "ingesting"
    FINALIZED = "finalized"


class SpanKind(StrEnum):
    """Provider-neutral span semantic category (docs/ARCHITECTURE.md's
    OpenTelemetry-interoperability boundary): callers map their
    provider-specific span shape onto this fixed vocabulary rather than
    EvalForge depending on a vendor's schema directly."""

    LLM_CALL = "llm_call"
    RETRIEVAL_CALL = "retrieval_call"
    TOOL_CALL = "tool_call"
    WORKFLOW_STEP = "workflow_step"
    OTHER = "other"


class SpanStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
