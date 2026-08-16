from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
import pytest

from evalforge_sdk.client import EvalForgeClient


@dataclass
class RecordingTransport:
    """A minimal fake HTTP backend: records every request it sees and
    replays a caller-configured response, so SDK tests never need a
    live EvalForge server or network access."""

    handler: Callable[[httpx.Request], httpx.Response]
    requests: list[httpx.Request] = field(default_factory=list)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler(request)


def json_response(status_code: int, body: dict[str, object]) -> httpx.Response:
    return httpx.Response(status_code, json=body)


def error_response(status_code: int, *, code: str, message: str) -> httpx.Response:
    return json_response(
        status_code,
        {"error": {"error_id": "test-error-id", "code": code, "message": message}},
    )


@pytest.fixture
def recording_transport() -> RecordingTransport:
    return RecordingTransport(handler=lambda request: json_response(200, {}))


@pytest.fixture
def make_client(
    recording_transport: RecordingTransport,
) -> Callable[..., EvalForgeClient]:
    def _make(*, timeout: float = 30.0) -> EvalForgeClient:
        return EvalForgeClient(
            base_url="https://api.evalforge.example",
            access_token="test-token",
            timeout=timeout,
            transport=httpx.MockTransport(recording_transport),
        )

    return _make


def last_request_json(transport: RecordingTransport) -> dict[str, object]:
    body: dict[str, object] = json.loads(transport.requests[-1].content)
    return body
