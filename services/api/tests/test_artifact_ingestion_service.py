from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest

from evalforge_api.adapters.postgres_pool import create_pool
from evalforge_api.application import artifact_ingestion_service
from evalforge_api.domain.hashing import hash_bytes
from evalforge_api.domain.ingestion import (
    IdempotencyConflictError,
    PayloadTooLargeError,
    compute_request_fingerprint,
)
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.settings import Settings
from test_run_ingestion import bootstrap_run_tenant

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]


def _fingerprint(*, purpose: str, body: bytes) -> str:
    return compute_request_fingerprint({"purpose": purpose, "content_hash": hash_bytes(body)})


async def test_upload_artifact_creates_a_new_version(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
    test_settings: Settings,
) -> None:
    context, workspace_id = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="up1@example.com",
    )
    pool = await create_pool(str(test_settings.app_database_url))
    try:
        body = b"hello ingestion artifact"
        version, created = await artifact_ingestion_service.upload_artifact(
            context=context,
            workspace_id=workspace_id,
            media_type="text/plain",
            purpose="log",
            body=body,
            max_bytes=1_000_000,
            idempotency_key="upload-1",
            request_fingerprint=_fingerprint(purpose="log", body=body),
            repositories=evaluation_repositories,
            db_pool=pool,
        )
        assert created is True
        assert version.byte_size == len(body)
        assert version.content_hash == hash_bytes(body)
    finally:
        await pool.close()


async def test_upload_artifact_oversized_is_rejected(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
    test_settings: Settings,
) -> None:
    context, workspace_id = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="up2@example.com",
    )
    pool = await create_pool(str(test_settings.app_database_url))
    try:
        body = b"x" * 100
        with pytest.raises(PayloadTooLargeError):
            await artifact_ingestion_service.upload_artifact(
                context=context,
                workspace_id=workspace_id,
                media_type="text/plain",
                purpose="log",
                body=body,
                max_bytes=10,
                idempotency_key="upload-oversized",
                request_fingerprint=_fingerprint(purpose="log", body=body),
                repositories=evaluation_repositories,
                db_pool=pool,
            )
    finally:
        await pool.close()


async def test_upload_artifact_same_key_same_payload_is_idempotent(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
    test_settings: Settings,
) -> None:
    context, workspace_id = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="up3@example.com",
    )
    pool = await create_pool(str(test_settings.app_database_url))
    try:
        body = b"idempotent-artifact-bytes"
        fingerprint = _fingerprint(purpose="log", body=body)
        first, first_created = await artifact_ingestion_service.upload_artifact(
            context=context,
            workspace_id=workspace_id,
            media_type="text/plain",
            purpose="log",
            body=body,
            max_bytes=1_000_000,
            idempotency_key="fixed-upload-key",
            request_fingerprint=fingerprint,
            repositories=evaluation_repositories,
            db_pool=pool,
        )
        second, second_created = await artifact_ingestion_service.upload_artifact(
            context=context,
            workspace_id=workspace_id,
            media_type="text/plain",
            purpose="log",
            body=body,
            max_bytes=1_000_000,
            idempotency_key="fixed-upload-key",
            request_fingerprint=fingerprint,
            repositories=evaluation_repositories,
            db_pool=pool,
        )
        assert first_created is True
        assert second_created is False
        assert first.id == second.id
    finally:
        await pool.close()


async def test_upload_artifact_same_key_different_payload_conflicts(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
    test_settings: Settings,
) -> None:
    context, workspace_id = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="up4@example.com",
    )
    pool = await create_pool(str(test_settings.app_database_url))
    try:
        await artifact_ingestion_service.upload_artifact(
            context=context,
            workspace_id=workspace_id,
            media_type="text/plain",
            purpose="log",
            body=b"first-payload",
            max_bytes=1_000_000,
            idempotency_key="conflict-upload-key",
            request_fingerprint=_fingerprint(purpose="log", body=b"first-payload"),
            repositories=evaluation_repositories,
            db_pool=pool,
        )
        with pytest.raises(IdempotencyConflictError):
            await artifact_ingestion_service.upload_artifact(
                context=context,
                workspace_id=workspace_id,
                media_type="text/plain",
                purpose="log",
                body=b"second-payload",
                max_bytes=1_000_000,
                idempotency_key="conflict-upload-key",
                request_fingerprint=_fingerprint(purpose="log", body=b"second-payload"),
                repositories=evaluation_repositories,
                db_pool=pool,
            )
    finally:
        await pool.close()
