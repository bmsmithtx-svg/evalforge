"""S3-compatible object-storage connectivity adapter."""

from __future__ import annotations

import asyncio

import boto3
import structlog
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from evalforge_api.ports.connectivity import ConnectivityResult

logger = structlog.get_logger(__name__)


class ObjectStorageConnectivityCheck:
    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str,
        timeout_seconds: float,
    ) -> None:
        self._endpoint_url = endpoint_url
        self._access_key = access_key
        self._secret_key = secret_key
        self._bucket = bucket
        self._region = region
        self._timeout_seconds = timeout_seconds

    def _head_bucket_sync(self) -> None:
        client = boto3.client(
            "s3",
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=self._region,
            config=BotoConfig(
                connect_timeout=self._timeout_seconds,
                read_timeout=self._timeout_seconds,
                retries={"max_attempts": 1},
            ),
        )
        client.head_bucket(Bucket=self._bucket)

    async def check(self) -> ConnectivityResult:
        try:
            await asyncio.to_thread(self._head_bucket_sync)
        except (BotoCoreError, ClientError, OSError) as exc:
            logger.warning("object_storage_connectivity_check_failed", error=type(exc).__name__)
            return ConnectivityResult(name="object_storage", ok=False, detail=type(exc).__name__)

        return ConnectivityResult(name="object_storage", ok=True)
