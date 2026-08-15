"""Redis connectivity adapter."""

from __future__ import annotations

import redis.asyncio as redis_asyncio
import structlog
from redis.exceptions import RedisError

from evalforge_api.ports.connectivity import ConnectivityResult

logger = structlog.get_logger(__name__)


class RedisConnectivityCheck:
    def __init__(self, url: str, *, timeout_seconds: float) -> None:
        self._url = url
        self._timeout_seconds = timeout_seconds

    async def check(self) -> ConnectivityResult:
        client = redis_asyncio.from_url(  # type: ignore[no-untyped-call]
            self._url,
            socket_connect_timeout=self._timeout_seconds,
            socket_timeout=self._timeout_seconds,
        )
        try:
            await client.ping()
        except (OSError, RedisError) as exc:
            logger.warning("redis_connectivity_check_failed", error=type(exc).__name__)
            return ConnectivityResult(name="redis", ok=False, detail=type(exc).__name__)
        finally:
            await client.aclose()

        return ConnectivityResult(name="redis", ok=True)
