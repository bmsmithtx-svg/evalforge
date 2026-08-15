"""Liveness endpoint.

Reports only that the process is running and serving requests. It must
not perform dependency I/O — that is the readiness endpoint's job — so
a slow downstream dependency cannot make an otherwise-healthy process
look dead to an orchestrator.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["foundation"])


@router.get("/healthz")
async def get_health() -> dict[str, str]:
    return {"status": "ok"}
