from __future__ import annotations

import httpx
import pytest

from evalforge_sdk.client import EvalForgeClient
from evalforge_sdk.exceptions import EvalForgeTimeoutError
from evalforge_sdk.transport import DEFAULT_TIMEOUT_SECONDS


def test_base_url_trailing_slash_is_normalized() -> None:
    client = EvalForgeClient(
        base_url="https://api.evalforge.example/",
        access_token="t",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )
    assert str(client._client.base_url) == "https://api.evalforge.example"  # noqa: SLF001


def test_default_timeout_is_applied() -> None:
    client = EvalForgeClient(
        base_url="https://api.evalforge.example",
        access_token="t",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )
    assert client._client.timeout.connect == DEFAULT_TIMEOUT_SECONDS  # noqa: SLF001


def test_custom_timeout_is_applied() -> None:
    client = EvalForgeClient(
        base_url="https://api.evalforge.example",
        access_token="t",
        timeout=5.0,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )
    assert client._client.timeout.connect == 5.0  # noqa: SLF001


async def test_context_manager_closes_the_client_on_exit() -> None:
    async with EvalForgeClient(
        base_url="https://api.evalforge.example",
        access_token="t",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    ) as client:
        assert not client._client.is_closed  # noqa: SLF001
    assert client._client.is_closed  # noqa: SLF001


async def test_no_automatic_retry_on_timeout() -> None:
    """The SDK does not retry a failed request on the caller's behalf —
    only one request should ever reach the transport."""
    call_count = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        raise httpx.ConnectTimeout("simulated timeout", request=request)

    async with EvalForgeClient(
        base_url="https://api.evalforge.example",
        access_token="t",
        transport=httpx.MockTransport(_handler),
    ) as client:
        with pytest.raises(EvalForgeTimeoutError):
            await client._request_json("GET", "/x")  # noqa: SLF001

    assert call_count == 1
