from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from conftest import RecordingTransport, json_response, last_request_json
from evalforge_sdk.client import EvalForgeClient
from evalforge_sdk.spans import SpanInput, SpanRecord

_SPAN_JSON = {
    "id": str(uuid4()),
    "trace_id": str(uuid4()),
    "parent_span_id": None,
    "provider_span_id": "root",
    "name": "llm-call",
    "span_kind": "llm_call",
    "status": "ok",
    "started_at": datetime.now(UTC).isoformat(),
    "ended_at": None,
    "attributes": {},
    "created_at": datetime.now(UTC).isoformat(),
}


async def test_ingest_spans_posts_the_batch_to_the_expected_path(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    recording_transport.handler = lambda request: json_response(200, [_SPAN_JSON])  # noqa: ARG005
    tenant_id, trace_id = uuid4(), uuid4()
    span = SpanInput(
        span_id="root", name="llm-call", span_kind="llm_call", started_at=datetime.now(UTC)
    )

    async with make_client() as client:
        spans = await client.ingest_spans(
            tenant_id=tenant_id, trace_id=trace_id, spans=(span,), idempotency_key="k"
        )

    request = recording_transport.requests[-1]
    assert request.url.path == f"/tenants/{tenant_id}/traces/{trace_id}/spans"
    assert len(spans) == 1
    assert isinstance(spans[0], SpanRecord)
    assert spans[0].provider_span_id == "root"


async def test_ingest_spans_body_includes_every_span(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    recording_transport.handler = lambda request: json_response(200, [_SPAN_JSON, _SPAN_JSON])  # noqa: ARG005
    root = SpanInput(
        span_id="root", name="root", span_kind="llm_call", started_at=datetime.now(UTC)
    )
    child = SpanInput(
        span_id="child",
        parent_span_id="root",
        name="child",
        span_kind="tool_call",
        started_at=datetime.now(UTC),
    )

    async with make_client() as client:
        await client.ingest_spans(
            tenant_id=uuid4(), trace_id=uuid4(), spans=(root, child), idempotency_key="k"
        )

    body = last_request_json(recording_transport)
    assert len(body["spans"]) == 2  # type: ignore[arg-type]
    assert body["spans"][0]["span_id"] == "root"  # type: ignore[index]
    assert body["spans"][1]["parent_span_id"] == "root"  # type: ignore[index]


async def test_list_spans_issues_a_get_request(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    recording_transport.handler = lambda request: json_response(200, [_SPAN_JSON])  # noqa: ARG005
    tenant_id, trace_id = uuid4(), uuid4()

    async with make_client() as client:
        spans = await client.list_spans(tenant_id=tenant_id, trace_id=trace_id)

    request = recording_transport.requests[-1]
    assert request.method == "GET"
    assert request.url.path == f"/tenants/{tenant_id}/traces/{trace_id}/spans"
    assert len(spans) == 1
