from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import pytest

from evalforge_api.application import trace_service
from evalforge_api.application.trace_service import AuthorizationDeniedError, RunNotFoundError
from evalforge_api.domain.enums import TenantRole
from evalforge_api.domain.hashing import hash_canonical_content
from evalforge_api.domain.ingestion_enums import TraceStatus
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from test_run_ingestion import bootstrap_run_tenant, create_run

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]


async def make_trace(
    *,
    context: TenantContext,
    run_id: UUID,
    ingestion_repositories: IngestionRepositories,
    idempotency_key: str = "trace-key-1",
    request_fingerprint: str | None = None,
) -> tuple[object, bool]:
    return await trace_service.create_trace(
        context=context,
        run_id=run_id,
        source="pytest-sdk",
        provider_trace_id=None,
        correlation_id=None,
        metadata={"case": "trace"},
        schema_version="trace-v1",
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint or hash_canonical_content({"key": idempotency_key}),
        ingestion_repositories=ingestion_repositories,
    )


async def test_developer_can_ingest_a_trace_for_its_own_run(
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
        email="tdev@example.com",
    )
    run, _created = await create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    trace, created = await make_trace(
        context=context, run_id=run.id, ingestion_repositories=ingestion_repositories
    )
    assert created is True
    assert trace.status == TraceStatus.INGESTING
    assert trace.run_id == run.id
    assert trace.workspace_id == workspace_id  # derived from the run, not caller-supplied


async def test_reviewer_cannot_ingest_a_trace(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    admin_context, workspace_id = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="treviewer@example.com",
        role=TenantRole.TENANT_ADMIN,
    )
    run, _created = await create_run(
        context=admin_context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    reviewer_context = build_tenant_context(
        tenant_id=admin_context.tenant_id,
        user_id=admin_context.user_id,
        role=TenantRole.REVIEWER,
    )
    with pytest.raises(AuthorizationDeniedError):
        await make_trace(
            context=reviewer_context, run_id=run.id, ingestion_repositories=ingestion_repositories
        )


async def test_trace_creation_requires_an_existing_run(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context, _workspace_id = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="norun@example.com",
    )
    with pytest.raises(RunNotFoundError):
        await make_trace(
            context=context, run_id=uuid4(), ingestion_repositories=ingestion_repositories
        )


async def test_cross_tenant_run_reference_is_rejected(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context_a, workspace_a = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="ta@example.com",
    )
    context_b, workspace_b = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-b",
        email="tb@example.com",
    )
    run_b, _created = await create_run(
        context=context_b,
        workspace_id=workspace_b,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    with pytest.raises(RunNotFoundError):
        await make_trace(
            context=context_a, run_id=run_b.id, ingestion_repositories=ingestion_repositories
        )
