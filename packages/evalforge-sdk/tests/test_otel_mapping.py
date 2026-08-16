from __future__ import annotations

from datetime import UTC, datetime

from evalforge_sdk.otel_mapping import otel_span_to_span_input


def test_maps_required_fields() -> None:
    otel_span = {
        "span_id": "abc123",
        "name": "chat.completions.create",
        "start_time_unix_nano": 1_700_000_000_000_000_000,
    }

    span = otel_span_to_span_input(otel_span, span_kind="llm_call")

    assert span.span_id == "abc123"
    assert span.name == "chat.completions.create"
    assert span.span_kind == "llm_call"
    assert span.parent_span_id is None
    assert span.started_at == datetime.fromtimestamp(1_700_000_000, tz=UTC)


def test_maps_parent_and_end_time() -> None:
    otel_span = {
        "span_id": "child",
        "parent_span_id": "parent",
        "name": "retrieve",
        "start_time_unix_nano": 1_700_000_000_000_000_000,
        "end_time_unix_nano": 1_700_000_001_000_000_000,
    }

    span = otel_span_to_span_input(otel_span, span_kind="retrieval_call")

    assert span.parent_span_id == "parent"
    assert span.ended_at == datetime.fromtimestamp(1_700_000_001, tz=UTC)


def test_maps_error_status() -> None:
    otel_span = {
        "span_id": "failed",
        "name": "tool.call",
        "start_time_unix_nano": 1_700_000_000_000_000_000,
        "status": {"code": "ERROR", "message": "boom"},
    }

    span = otel_span_to_span_input(otel_span, span_kind="tool_call")

    assert span.status == "error"
    assert span.error_message == "boom"


def test_defaults_to_ok_status_when_unspecified() -> None:
    otel_span = {
        "span_id": "ok-span",
        "name": "step",
        "start_time_unix_nano": 1_700_000_000_000_000_000,
    }

    span = otel_span_to_span_input(otel_span, span_kind="workflow_step")

    assert span.status == "ok"
    assert span.error_message is None


def test_carries_attributes_through_unchanged() -> None:
    otel_span = {
        "span_id": "attrs",
        "name": "step",
        "start_time_unix_nano": 1_700_000_000_000_000_000,
        "attributes": {"model": "gpt-x", "temperature": 0.2},
    }

    span = otel_span_to_span_input(otel_span, span_kind="llm_call")

    assert span.attributes == {"model": "gpt-x", "temperature": 0.2}
