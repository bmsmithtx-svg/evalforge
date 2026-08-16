from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from conftest import RecordingTransport, json_response
from evalforge_sdk.client import EvalForgeClient
from evalforge_sdk.traces import TraceFinalizeInput, TraceInput, TraceRecord

_TRACE_JSON = {
    "id": str(uuid4()),
    "tenant_id": str(uuid4()),
    "workspace_id": str(uuid4()),
    "run_id": str(uuid4()),
    "status": "ingesting",
    "source": "sdk-test",
    "metadata": {},
    "created_at": datetime.now(UTC).isoformat(),
}


async def test_create_trace_posts_to_the_expected_path(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    recording_transport.handler = lambda request: json_response(201, _TRACE_JSON)  # noqa: ARG005
    tenant_id = uuid4()
    trace_input = TraceInput(run_id=uuid4(), source="sdk-test")

    async with make_client() as client:
        trace = await client.create_trace(
            tenant_id=tenant_id, trace=trace_input, idempotency_key="k"
        )

    request = recording_transport.requests[-1]
    assert request.url.path == f"/tenants/{tenant_id}/traces"
    assert isinstance(trace, TraceRecord)


async def test_finalize_trace_posts_to_the_finalize_path(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    finalized = {**_TRACE_JSON, "status": "finalized"}
    recording_transport.handler = lambda request: json_response(200, finalized)  # noqa: ARG005
    tenant_id, trace_id = uuid4(), uuid4()

    async with make_client() as client:
        trace = await client.finalize_trace(
            tenant_id=tenant_id,
            trace_id=trace_id,
            finalize=TraceFinalizeInput(),
            idempotency_key="k",
        )

    request = recording_transport.requests[-1]
    assert request.url.path == f"/tenants/{tenant_id}/traces/{trace_id}/finalize"
    assert trace.status == "finalized"


async def test_get_trace_issues_a_get_request(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    recording_transport.handler = lambda request: json_response(200, _TRACE_JSON)  # noqa: ARG005
    tenant_id, trace_id = uuid4(), uuid4()

    async with make_client() as client:
        trace = await client.get_trace(tenant_id=tenant_id, trace_id=trace_id)

    request = recording_transport.requests[-1]
    assert request.method == "GET"
    assert str(trace.run_id) == _TRACE_JSON["run_id"]
