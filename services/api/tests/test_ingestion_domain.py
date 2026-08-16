from __future__ import annotations

import pytest

from evalforge_api.domain.ingestion import (
    MAX_METADATA_BYTES,
    MAX_SPANS_PER_BATCH,
    ImmutableRunError,
    ImmutableTraceError,
    PayloadTooLargeError,
    SpanBatchTooLargeError,
    compute_request_fingerprint,
    ensure_run_is_active,
    ensure_trace_is_ingesting,
    validate_metadata_size,
    validate_span_batch_size,
)
from evalforge_api.domain.ingestion_enums import RunStatus, TraceStatus


def test_ensure_run_is_active_allows_running() -> None:
    ensure_run_is_active(RunStatus.RUNNING)  # must not raise


@pytest.mark.parametrize("status", [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELED])
def test_ensure_run_is_active_rejects_terminal_statuses(status: RunStatus) -> None:
    with pytest.raises(ImmutableRunError):
        ensure_run_is_active(status)


def test_ensure_trace_is_ingesting_allows_ingesting() -> None:
    ensure_trace_is_ingesting(TraceStatus.INGESTING)  # must not raise


def test_ensure_trace_is_ingesting_rejects_finalized() -> None:
    with pytest.raises(ImmutableTraceError):
        ensure_trace_is_ingesting(TraceStatus.FINALIZED)


def test_validate_span_batch_size_rejects_empty_batch() -> None:
    with pytest.raises(SpanBatchTooLargeError):
        validate_span_batch_size(0)


def test_validate_span_batch_size_rejects_oversized_batch() -> None:
    with pytest.raises(SpanBatchTooLargeError):
        validate_span_batch_size(MAX_SPANS_PER_BATCH + 1)


def test_validate_span_batch_size_allows_the_maximum() -> None:
    validate_span_batch_size(MAX_SPANS_PER_BATCH)  # must not raise


def test_validate_metadata_size_rejects_oversized_metadata() -> None:
    huge = {"blob": "x" * MAX_METADATA_BYTES}
    with pytest.raises(PayloadTooLargeError):
        validate_metadata_size(huge)


def test_validate_metadata_size_allows_small_metadata() -> None:
    validate_metadata_size({"note": "small"})  # must not raise


def test_compute_request_fingerprint_is_deterministic_regardless_of_key_order() -> None:
    first = compute_request_fingerprint({"a": 1, "b": 2})
    second = compute_request_fingerprint({"b": 2, "a": 1})
    assert first == second


def test_compute_request_fingerprint_changes_with_content() -> None:
    first = compute_request_fingerprint({"a": 1})
    second = compute_request_fingerprint({"a": 2})
    assert first != second
