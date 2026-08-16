"""The public EvalForge SDK client.

Configuration is explicit and comes only from the caller — the EvalForge
API base URL and an already-issued bearer access token (obtained
through ``POST /auth/login`` or an equivalent authorized flow). No
credential is ever hardcoded or read from an implicit location; the
caller decides how to source it (environment variable, secret manager,
etc.).
"""

from __future__ import annotations

import httpx

from evalforge_sdk.artifacts import ArtifactsClientMixin
from evalforge_sdk.runs import RunsClientMixin
from evalforge_sdk.spans import SpansClientMixin
from evalforge_sdk.traces import TracesClientMixin
from evalforge_sdk.transport import DEFAULT_TIMEOUT_SECONDS, EvalForgeTransport


class EvalForgeClient(
    RunsClientMixin,
    TracesClientMixin,
    SpansClientMixin,
    ArtifactsClientMixin,
    EvalForgeTransport,
):
    """Async client for the EvalForge Milestone 5 ingestion API.

    Example::

        async with EvalForgeClient(
            base_url="https://api.evalforge.example", access_token=token
        ) as client:
            run = await client.create_run(tenant_id=tenant_id, run=run_input)

    Every write method accepts an optional ``idempotency_key``; reusing
    the same key for the same effective request returns the original
    result instead of creating duplicate evidence. If omitted, a fresh
    key is generated per call, so repeated calls are *not* implicitly
    deduplicated — callers that want retry-safety must supply and reuse
    their own key.
    """

    def __init__(
        self,
        *,
        base_url: str,
        access_token: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url, access_token=access_token, timeout=timeout, transport=transport
        )
