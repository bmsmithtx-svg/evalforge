"""S3-compatible object-storage adapter for artifact bytes.

Tenant scoping is the caller's responsibility — see
``evalforge_api.application.artifact_service`` for tenant-scoped key
construction from server-verified identity; this adapter only knows
how to move bytes to and from the configured bucket by key. Objects
are never written with a public ACL, so tenant artifacts are private
by default regardless of caller behavior.
"""

from __future__ import annotations

import asyncio

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

_NOT_FOUND_CODES = {"NoSuchKey", "404", "NotFound"}


class ArtifactNotFoundError(Exception):
    pass


class S3ArtifactObjectStorage:
    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str,
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=BotoConfig(signature_version="s3v4"),
        )

    def _put_object_sync(self, *, key: str, body: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=body, ContentType=content_type)

    def _get_object_sync(self, *, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in _NOT_FOUND_CODES:
                raise ArtifactNotFoundError(key) from exc
            raise
        body: bytes = response["Body"].read()
        return body

    def _object_exists_sync(self, *, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in _NOT_FOUND_CODES:
                return False
            raise
        return True

    async def put_object(self, *, key: str, body: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._put_object_sync, key=key, body=body, content_type=content_type
        )

    async def get_object(self, *, key: str) -> bytes:
        return await asyncio.to_thread(self._get_object_sync, key=key)

    async def object_exists(self, *, key: str) -> bool:
        return await asyncio.to_thread(self._object_exists_sync, key=key)
