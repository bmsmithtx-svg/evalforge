"""In-process fixed-window rate limiting.

Foundation-level backpressure only: state is per-process and resets on
restart. A distributed, Redis-backed limiter is expected to replace
this once multiple API processes run behind a shared load balancer.
"""

from __future__ import annotations

import time
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.status import HTTP_429_TOO_MANY_REQUESTS


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: object,
        *,
        max_requests: int,
        window_seconds: float,
        exempt_paths: frozenset[str] = frozenset(),
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._exempt_paths = exempt_paths
        self._request_times: dict[str, deque[float]] = {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self._exempt_paths:
            return await call_next(request)

        client_key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self._request_times.setdefault(client_key, deque())

        while window and now - window[0] > self._window_seconds:
            window.popleft()

        if len(window) >= self._max_requests:
            retry_after = max(0.0, self._window_seconds - (now - window[0]))
            return JSONResponse(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(int(retry_after) + 1)},
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many requests. Retry after the window elapses.",
                    }
                },
            )

        window.append(now)
        return await call_next(request)
