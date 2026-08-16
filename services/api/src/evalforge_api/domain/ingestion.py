"""Ingestion-boundary policy: immutability, batch bounds, and the
idempotency request-fingerprint contract.

Pure domain rules with no persistence dependency, matching
``evalforge_api.domain.versioning``. The PostgreSQL layer enforces the
same immutability invariants independently (triggers and privilege
grants) — this module is the first line of defense and unit-testable
without a database. See docs/SECURITY_BASELINE.md ("Rate limiting and
quotas") and docs/THREAT_MODEL.md ("Trace and artifact poisoning",
"Replay attacks").
"""

from __future__ import annotations

from evalforge_api.domain.hashing import canonicalize_json, hash_canonical_content
from evalforge_api.domain.ingestion_enums import TERMINAL_RUN_STATUSES, RunStatus, TraceStatus

# Bounded collections: an ingestion endpoint must never accept an
# unbounded number of spans or an unbounded metadata payload in one
# request (docs/SECURITY_BASELINE.md).
MAX_SPANS_PER_BATCH = 500
MAX_METADATA_BYTES = 16_000
MAX_ATTRIBUTES_BYTES = 8_000


class ImmutableRunError(Exception):
    """Raised when code attempts to mutate a terminal, immutable run."""


class ImmutableTraceError(Exception):
    """Raised when code attempts to mutate a finalized, immutable trace."""


class SpanBatchTooLargeError(Exception):
    pass


class PayloadTooLargeError(Exception):
    pass


class SpanParentNotFoundError(Exception):
    """Raised when a span references a parent that is neither earlier
    in the same batch nor already persisted in the same trace."""


class IdempotencyConflictError(Exception):
    """Same idempotency key, materially different request."""

    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            f"Idempotency key {idempotency_key!r} was already used with a different request."
        )
        self.idempotency_key = idempotency_key


def ensure_run_is_active(status: RunStatus) -> None:
    """A run may only be finalized, or have lineage attached, while it
    has not yet reached a terminal state — reruns or materially
    different evidence must create a new run rather than rewriting
    completed historical evidence (docs/REPRODUCIBILITY_CONTRACT.md).
    """
    if status in TERMINAL_RUN_STATUSES:
        raise ImmutableRunError(f"Run is '{status.value}' and can no longer be modified.")


def ensure_trace_is_ingesting(status: TraceStatus) -> None:
    """Spans may only be appended, and finalization may only occur,
    while a trace is still accepting evidence."""
    if status != TraceStatus.INGESTING:
        raise ImmutableTraceError(f"Trace is '{status.value}' and can no longer accept new spans.")


def validate_span_batch_size(span_count: int) -> None:
    if span_count == 0:
        raise SpanBatchTooLargeError("A span batch must include at least one span.")
    if span_count > MAX_SPANS_PER_BATCH:
        raise SpanBatchTooLargeError(
            f"A span batch may include at most {MAX_SPANS_PER_BATCH} spans (received {span_count})."
        )


def _validate_json_bound(content: object, *, max_bytes: int, label: str) -> None:
    size = len(canonicalize_json(content))
    if size > max_bytes:
        raise PayloadTooLargeError(f"{label} exceeds the {max_bytes}-byte limit ({size} bytes).")


def validate_metadata_size(metadata: dict[str, object]) -> None:
    _validate_json_bound(metadata, max_bytes=MAX_METADATA_BYTES, label="metadata")


def validate_attributes_size(attributes: dict[str, object]) -> None:
    _validate_json_bound(attributes, max_bytes=MAX_ATTRIBUTES_BYTES, label="span attributes")


def compute_request_fingerprint(payload: dict[str, object]) -> str:
    """A deterministic fingerprint of an ingestion request body, used to
    detect whether a repeated idempotency key carries the same
    "effective request" or a materially different one. Reuses the same
    canonical-JSON hashing used for evaluation-domain content hashes
    (docs/REPRODUCIBILITY_CONTRACT.md) rather than inventing a second
    hashing scheme.
    """
    return hash_canonical_content(payload)
