from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from evalforge_api.middleware.rate_limit import RateLimitMiddleware


async def _echo(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


def _build_client(max_requests: int) -> TestClient:
    app = Starlette(routes=[Route("/echo", _echo)])
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=max_requests,
        window_seconds=60.0,
        exempt_paths=frozenset({"/healthz"}),
    )
    return TestClient(app)


def test_requests_within_limit_succeed() -> None:
    client = _build_client(max_requests=3)
    for _ in range(3):
        assert client.get("/echo").status_code == 200


def test_requests_over_limit_are_rejected_with_429() -> None:
    client = _build_client(max_requests=2)
    assert client.get("/echo").status_code == 200
    assert client.get("/echo").status_code == 200
    third = client.get("/echo")
    assert third.status_code == 429
    assert "Retry-After" in third.headers
