"""Standardized error-response boundary.

Every error response — validation failure, unhandled exception, or an
explicit ``HTTPException`` — is rendered through this module so callers
receive one consistent envelope and internal detail never leaks into a
response body.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = structlog.get_logger(__name__)


def _error_body(*, error_id: str, code: str, message: str, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error_id": error_id, "code": code, "message": message}
    if details is not None:
        body["details"] = details
    return {"error": body}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        error_id = str(uuid.uuid4())
        logger.info(
            "request_validation_failed",
            error_id=error_id,
            path=request.url.path,
            errors=exc.errors(),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_body(
                error_id=error_id,
                code="validation_error",
                message="The request did not match the expected schema.",
                # Custom Pydantic validators can raise arbitrary
                # exceptions, and exc.errors() embeds them verbatim
                # under ctx.error — jsonable_encoder makes the whole
                # structure JSON-safe instead of erroring mid-response.
                details=jsonable_encoder(exc.errors()),
            ),
        )

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        error_id = str(uuid.uuid4())
        logger.info(
            "http_exception",
            error_id=error_id,
            path=request.url.path,
            status_code=exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(
                error_id=error_id,
                code=_code_for_status(exc.status_code),
                message=str(exc.detail),
            ),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        error_id = str(uuid.uuid4())
        logger.error(
            "unhandled_exception",
            error_id=error_id,
            path=request.url.path,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                error_id=error_id,
                code="internal_error",
                message="An unexpected error occurred. Reference the error_id when reporting it.",
            ),
        )


def _code_for_status(status_code: int) -> str:
    return {
        status.HTTP_400_BAD_REQUEST: "bad_request",
        status.HTTP_401_UNAUTHORIZED: "unauthorized",
        status.HTTP_403_FORBIDDEN: "forbidden",
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_409_CONFLICT: "conflict",
        status.HTTP_413_CONTENT_TOO_LARGE: "payload_too_large",
        status.HTTP_422_UNPROCESSABLE_CONTENT: "validation_error",
        status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
    }.get(status_code, "error")
