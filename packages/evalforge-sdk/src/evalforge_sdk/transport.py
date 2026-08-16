"""Core EvalForge SDK transport: authentication and low-level HTTP
request/response handling.

Every ingestion-domain mixin (runs.py, traces.py, spans.py,
artifacts.py) calls ``_send``/``_request_json`` here — this is the one
place that knows about httpx, bearer-token auth headers, and
standardized-error-response parsing, keeping transport mechanics
separate from ingestion domain semantics.

No automatic retries: a network failure or timeout is surfaced to the
caller as a typed exception rather than silently retried, since
retrying a write is only safe when the caller controls the idempotency
key — this module never decides that on the caller's behalf.
"""

from __future__ import annotations

from typing import Any, Self

import httpx

from evalforge_sdk.exceptions import (
    EvalForgeAPIError,
    EvalForgeConnectionError,
    EvalForgeTimeoutError,
)

DEFAULT_TIMEOUT_SECONDS = 30.0


def _raise_for_error_response(response: httpx.Response) -> None:
    try:
        body = response.json()
        error = body.get("error", {})
        code = str(error.get("code", "unknown_error"))
        message = str(error.get("message", response.text))
        error_id = error.get("error_id")
    except ValueError:
        code, message, error_id = "unknown_error", response.text, None
    raise EvalForgeAPIError(
        status_code=response.status_code, code=code, message=message, error_id=error_id
    )


class EvalForgeTransport:
    """Low-level authenticated HTTP transport. Not intended for direct
    use — construct ``evalforge_sdk.EvalForgeClient`` instead."""

    def __init__(
        self,
        *,
        base_url: str,
        access_token: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """``transport`` overrides the network layer — intended for
        tests (e.g. ``httpx.MockTransport``), not production use."""
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=httpx.Timeout(timeout), transport=transport
        )
        self._access_token = access_token

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    def _headers(self, *, idempotency_key: str | None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._access_token}"}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    async def _send(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> httpx.Response:
        try:
            response = await self._client.request(
                method,
                path,
                json=json_body,
                files=files,
                data=data,
                headers=self._headers(idempotency_key=idempotency_key),
            )
        except httpx.TimeoutException as exc:
            raise EvalForgeTimeoutError(f"Request to {path} timed out.") from exc
        except httpx.HTTPError as exc:
            raise EvalForgeConnectionError(f"Could not reach {path}: {exc}") from exc

        if response.status_code >= 400:
            _raise_for_error_response(response)
        return response

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        response = await self._send(
            method, path, json_body=json_body, idempotency_key=idempotency_key
        )
        result: dict[str, Any] = response.json()
        return result

    async def _request_json_list(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> list[dict[str, Any]]:
        response = await self._send(
            method, path, json_body=json_body, idempotency_key=idempotency_key
        )
        result: list[dict[str, Any]] = response.json()
        return result
