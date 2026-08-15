"""Connectivity-check ports for Milestone 2 foundation dependencies.

Milestone 2 authorizes connectivity verification only, not domain
persistence. Each protocol exposes a single ``check`` coroutine so the
readiness route can depend on an interface rather than a concrete
PostgreSQL, Redis, or object-storage client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ConnectivityResult:
    name: str
    ok: bool
    detail: str | None = None


class ConnectivityCheck(Protocol):
    """A single dependency's connectivity probe."""

    async def check(self) -> ConnectivityResult: ...
