"""Reject request bodies larger than the configured limit."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.status import HTTP_413_CONTENT_TOO_LARGE


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, *, max_body_bytes: int) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_bytes = int(content_length)
            except ValueError:
                declared_bytes = None
            if declared_bytes is not None and declared_bytes > self._max_body_bytes:
                return _too_large_response(self._max_body_bytes)

        body = await request.body()
        if len(body) > self._max_body_bytes:
            return _too_large_response(self._max_body_bytes)

        return await call_next(request)


def _too_large_response(max_body_bytes: int) -> JSONResponse:
    return JSONResponse(
        status_code=HTTP_413_CONTENT_TOO_LARGE,
        content={
            "error": {
                "code": "payload_too_large",
                "message": f"Request body exceeds the {max_body_bytes}-byte limit.",
            }
        },
    )
