from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from evalforge_api.middleware.request_size_limit import RequestSizeLimitMiddleware


async def _echo(request: Request) -> PlainTextResponse:
    body = await request.body()
    return PlainTextResponse(f"received {len(body)} bytes")


def _build_client(max_body_bytes: int) -> TestClient:
    app = Starlette(routes=[Route("/echo", _echo, methods=["POST"])])
    app.add_middleware(RequestSizeLimitMiddleware, max_body_bytes=max_body_bytes)
    return TestClient(app)


def test_body_within_limit_is_accepted() -> None:
    client = _build_client(max_body_bytes=100)
    response = client.post("/echo", content=b"x" * 50)
    assert response.status_code == 200


def test_body_over_limit_is_rejected_with_413() -> None:
    client = _build_client(max_body_bytes=10)
    response = client.post("/echo", content=b"x" * 100)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
