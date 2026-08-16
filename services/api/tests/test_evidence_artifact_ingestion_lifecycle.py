from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

import asyncpg
import pytest

from evalforge_api.application import evidence_artifact_service
from evalforge_api.domain.ingestion import IdempotencyConflictError
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from evalforge_api.settings import Settings
from test_evidence_artifact_ingestion import make_artifact_version
from test_run_ingestion import bootstrap_run_tenant, create_run

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]


async def test_attach_same_key_same_payload_is_idempotent(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
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
        email="ev5@example.com",
    )
    run, _created = await create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    version_id = await make_artifact_version(
        context=context, workspace_id=workspace_id, repositories=evaluation_repositories
    )
    first, first_created = await evidence_artifact_service.attach_artifact(
        context=context,
        run_id=run.id,
        trace_id=None,
        artifact_version_id=version_id,
        role="log",
        idempotency_key="fixed-attach",
        request_fingerprint="fixed-attach-fp",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    second, second_created = await evidence_artifact_service.attach_artifact(
        context=context,
        run_id=run.id,
        trace_id=None,
        artifact_version_id=version_id,
        role="log",
        idempotency_key="fixed-attach",
        request_fingerprint="fixed-attach-fp",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    assert first_created is True
    assert second_created is False
    assert first.id == second.id

    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        count = await connection.fetchval(
            "SELECT count(*) FROM run_evidence_artifacts WHERE run_id = $1", run.id
        )
    finally:
        await connection.close()
    assert count == 1


async def test_attach_same_key_different_payload_conflicts(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context, workspace_id = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="ev6@example.com",
    )
    run, _created = await create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    version_id = await make_artifact_version(
        context=context, workspace_id=workspace_id, repositories=evaluation_repositories
    )
    await evidence_artifact_service.attach_artifact(
        context=context,
        run_id=run.id,
        trace_id=None,
        artifact_version_id=version_id,
        role="log",
        idempotency_key="conflict-attach",
        request_fingerprint="fp-one",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    with pytest.raises(IdempotencyConflictError):
        await evidence_artifact_service.attach_artifact(
            context=context,
            run_id=run.id,
            trace_id=None,
            artifact_version_id=version_id,
            role="different-role",
            idempotency_key="conflict-attach",
            request_fingerprint="fp-two",
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
        )
