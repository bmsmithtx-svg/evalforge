"""Reject request bodies larger than the configured limit."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.status import HTTP_413_CONTENT_TOO_LARGE


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: object,
        *,
        max_body_bytes: int,
        path_suffix_overrides: dict[str, int] | None = None,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._max_body_bytes = max_body_bytes
        # Milestone 5: multipart artifact uploads need a larger ceiling
        # than JSON command payloads without loosening the default for
        # every other endpoint (docs/SECURITY_BASELINE.md).
        self._path_suffix_overrides = path_suffix_overrides or {}

    def _limit_for(self, path: str) -> int:
        for suffix, limit in self._path_suffix_overrides.items():
            if path.endswith(suffix):
                return limit
        return self._max_body_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        limit = self._limit_for(request.url.path)
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_bytes = int(content_length)
            except ValueError:
                declared_bytes = None
            if declared_bytes is not None and declared_bytes > limit:
                return _too_large_response(limit)

        body = await request.body()
        if len(body) > limit:
            return _too_large_response(limit)

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
