"""Readiness endpoint.

Verifies PostgreSQL, Redis, and object-storage connectivity on demand.
Returns 200 only when every configured dependency check succeeds, and
503 with per-dependency detail otherwise.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request, Response, status

from evalforge_api.ports.connectivity import ConnectivityCheck, ConnectivityResult

router = APIRouter(tags=["foundation"])


@router.get("/readyz")
async def get_readiness(request: Request, response: Response) -> dict[str, object]:
    checks: list[ConnectivityCheck] = request.app.state.connectivity_checks
    results: tuple[ConnectivityResult, ...] = tuple(
        await asyncio.gather(*(check.check() for check in checks))
    )

    all_ok = all(result.ok for result in results)
    response.status_code = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if all_ok else "not_ready",
        "dependencies": [
            {"name": result.name, "ok": result.ok, "detail": result.detail} for result in results
        ],
    }
