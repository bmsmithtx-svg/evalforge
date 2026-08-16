from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from conftest import RecordingTransport, json_response
from evalforge_sdk.artifacts import ArtifactUploadResult
from evalforge_sdk.client import EvalForgeClient

_UPLOAD_JSON = {
    "artifact_id": str(uuid4()),
    "version_id": str(uuid4()),
    "version_number": 1,
    "content_hash": "a" * 64,
    "hash_algorithm": "sha256",
    "byte_size": 11,
    "content_type": "text/plain",
    "evidence_attached": False,
}


async def test_upload_artifact_sends_a_multipart_request(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    recording_transport.handler = lambda request: json_response(200, _UPLOAD_JSON)  # noqa: ARG005
    tenant_id = uuid4()

    async with make_client() as client:
        result = await client.upload_artifact(
            tenant_id=tenant_id,
            content=b"hello world",
            content_type="text/plain",
            purpose="log",
            idempotency_key="upload-k",
        )

    request = recording_transport.requests[-1]
    assert request.method == "POST"
    assert request.url.path == f"/tenants/{tenant_id}/artifacts"
    assert request.headers["content-type"].startswith("multipart/form-data")
    assert request.headers["idempotency-key"] == "upload-k"
    assert isinstance(result, ArtifactUploadResult)
    assert result.byte_size == 11


async def test_upload_artifact_includes_run_and_trace_form_fields_when_given(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    recording_transport.handler = lambda request: json_response(  # noqa: ARG005
        200, {**_UPLOAD_JSON, "evidence_attached": True}
    )
    run_id = uuid4()

    async with make_client() as client:
        result = await client.upload_artifact(
            tenant_id=uuid4(),
            content=b"evidence bytes",
            content_type="text/plain",
            purpose="log",
            run_id=run_id,
            idempotency_key="upload-k2",
        )

    body = recording_transport.requests[-1].content
    assert str(run_id).encode() in body
    assert result.evidence_attached is True
