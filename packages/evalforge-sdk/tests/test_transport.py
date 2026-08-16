from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from conftest import RecordingTransport, error_response, json_response
from evalforge_sdk.client import EvalForgeClient
from evalforge_sdk.exceptions import (
    EvalForgeAPIError,
    EvalForgeConnectionError,
    EvalForgeTimeoutError,
)


async def test_requests_carry_a_bearer_authorization_header(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    async with make_client() as client:
        await client._request_json("GET", "/healthz")  # noqa: SLF001 -- transport internals

    assert recording_transport.requests[-1].headers["authorization"] == "Bearer test-token"


async def test_idempotency_key_header_is_set_when_provided(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    async with make_client() as client:
        await client._request_json(  # noqa: SLF001 -- transport internals
            "POST", "/x", json_body={}, idempotency_key="my-key"
        )

    assert recording_transport.requests[-1].headers["idempotency-key"] == "my-key"


async def test_idempotency_key_header_is_absent_when_not_provided(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    async with make_client() as client:
        await client._request_json("GET", "/x")  # noqa: SLF001 -- transport internals

    assert "idempotency-key" not in recording_transport.requests[-1].headers


async def test_access_token_never_appears_in_a_request_body(
    make_client: Callable[..., EvalForgeClient], recording_transport: RecordingTransport
) -> None:
    async with make_client() as client:
        await client._request_json(  # noqa: SLF001 -- transport internals
            "POST", "/x", json_body={"a": 1}, idempotency_key="k"
        )

    assert b"test-token" not in recording_transport.requests[-1].content


async def test_error_response_is_translated_to_a_typed_exception(
    recording_transport: RecordingTransport, make_client: Callable[..., EvalForgeClient]
) -> None:
    recording_transport.handler = lambda request: error_response(  # noqa: ARG005
        403, code="forbidden", message="Not authorized to ingest a run."
    )
    async with make_client() as client:
        with pytest.raises(EvalForgeAPIError) as exc_info:
            await client._request_json("POST", "/x", json_body={})  # noqa: SLF001

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "forbidden"
    assert exc_info.value.error_id == "test-error-id"


async def test_non_json_error_body_still_raises_a_typed_exception(
    recording_transport: RecordingTransport, make_client: Callable[..., EvalForgeClient]
) -> None:
    recording_transport.handler = lambda request: httpx.Response(500, text="upstream failure")  # noqa: ARG005
    async with make_client() as client:
        with pytest.raises(EvalForgeAPIError) as exc_info:
            await client._request_json("GET", "/x")  # noqa: SLF001

    assert exc_info.value.status_code == 500


async def test_timeout_is_translated_to_a_typed_exception(
    recording_transport: RecordingTransport, make_client: Callable[..., EvalForgeClient]
) -> None:
    def _raise_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("simulated timeout", request=request)

    recording_transport.handler = _raise_timeout
    async with make_client() as client:
        with pytest.raises(EvalForgeTimeoutError):
            await client._request_json("GET", "/x")  # noqa: SLF001


async def test_connection_failure_is_translated_to_a_typed_exception(
    recording_transport: RecordingTransport, make_client: Callable[..., EvalForgeClient]
) -> None:
    def _raise_connect_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connection failure", request=request)

    recording_transport.handler = _raise_connect_error
    async with make_client() as client:
        with pytest.raises(EvalForgeConnectionError):
            await client._request_json("GET", "/x")  # noqa: SLF001


async def test_successful_response_is_returned_as_a_dict(
    recording_transport: RecordingTransport, make_client: Callable[..., EvalForgeClient]
) -> None:
    recording_transport.handler = lambda request: json_response(200, {"ok": True})  # noqa: ARG005
    async with make_client() as client:
        body = await client._request_json("GET", "/x")  # noqa: SLF001

    assert body == {"ok": True}


async def test_client_close_releases_the_underlying_http_client(
    make_client: Callable[..., EvalForgeClient],
) -> None:
    client = make_client()
    await client.aclose()
    assert client._client.is_closed  # noqa: SLF001 -- verifying cleanup, not calling behavior
