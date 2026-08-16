from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from conftest import RecordingTransport, json_response, last_request_json
from evalforge_sdk.client import EvalForgeClient
from evalforge_sdk.runs import RunFinalizeInput, RunInput, RunRecord

_RUN_JSON = {
    "id": str(uuid4()),
    "tenant_id": str(uuid4()),
    "workspace_id": str(uuid4()),
    "status": "running",
    "source": "sdk-test",
    "started_at": datetime.now(UTC).isoformat(),
    "ended_at": None,
    "metadata": {},
    "created_at": datetime.now(UTC).isoformat(),
}


async def test_create_run_posts_to_the_expected_path_with_a_bearer_token(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    recording_transport.handler = lambda request: json_response(201, _RUN_JSON)  # noqa: ARG005
    tenant_id = uuid4()
    run_input = RunInput(workspace_id=uuid4(), source="sdk-test", started_at=datetime.now(UTC))

    async with make_client() as client:
        run = await client.create_run(tenant_id=tenant_id, run=run_input, idempotency_key="k1")

    request = recording_transport.requests[-1]
    assert request.method == "POST"
    assert request.url.path == f"/tenants/{tenant_id}/runs"
    assert isinstance(run, RunRecord)
    assert str(run.id) == _RUN_JSON["id"]


async def test_create_run_without_an_explicit_key_still_sends_one(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    recording_transport.handler = lambda request: json_response(201, _RUN_JSON)  # noqa: ARG005
    run_input = RunInput(workspace_id=uuid4(), source="sdk-test", started_at=datetime.now(UTC))

    async with make_client() as client:
        await client.create_run(tenant_id=uuid4(), run=run_input)

    assert "idempotency-key" in recording_transport.requests[-1].headers
    assert recording_transport.requests[-1].headers["idempotency-key"] != ""


async def test_repeated_calls_without_an_explicit_key_use_different_keys(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    recording_transport.handler = lambda request: json_response(201, _RUN_JSON)  # noqa: ARG005
    run_input = RunInput(workspace_id=uuid4(), source="sdk-test", started_at=datetime.now(UTC))

    async with make_client() as client:
        await client.create_run(tenant_id=uuid4(), run=run_input)
        await client.create_run(tenant_id=uuid4(), run=run_input)

    first_key = recording_transport.requests[0].headers["idempotency-key"]
    second_key = recording_transport.requests[1].headers["idempotency-key"]
    assert first_key != second_key


async def test_run_input_serializes_optional_lineage_as_null_when_absent(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    recording_transport.handler = lambda request: json_response(201, _RUN_JSON)  # noqa: ARG005
    run_input = RunInput(workspace_id=uuid4(), source="sdk-test", started_at=datetime.now(UTC))

    async with make_client() as client:
        await client.create_run(tenant_id=uuid4(), run=run_input, idempotency_key="k2")

    body = last_request_json(recording_transport)
    assert body["model_version_id"] is None
    assert body["tool_definition_version_ids"] == []


async def test_finalize_run_posts_to_the_finalize_path(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    finalized_json = {**_RUN_JSON, "status": "completed"}
    recording_transport.handler = lambda request: json_response(200, finalized_json)  # noqa: ARG005
    tenant_id, run_id = uuid4(), uuid4()

    async with make_client() as client:
        run = await client.finalize_run(
            tenant_id=tenant_id,
            run_id=run_id,
            finalize=RunFinalizeInput(status="completed", ended_at=datetime.now(UTC)),
            idempotency_key="finalize-k",
        )

    request = recording_transport.requests[-1]
    assert request.url.path == f"/tenants/{tenant_id}/runs/{run_id}/finalize"
    assert run.status == "completed"


async def test_get_run_issues_a_get_request(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    recording_transport.handler = lambda request: json_response(200, _RUN_JSON)  # noqa: ARG005
    tenant_id, run_id = uuid4(), uuid4()

    async with make_client() as client:
        run = await client.get_run(tenant_id=tenant_id, run_id=run_id)

    request = recording_transport.requests[-1]
    assert request.method == "GET"
    assert request.url.path == f"/tenants/{tenant_id}/runs/{run_id}"
    assert str(run.id) == _RUN_JSON["id"]
