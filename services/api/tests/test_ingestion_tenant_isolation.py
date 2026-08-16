from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import asyncpg
import pytest

from evalforge_api.adapters.rls_session import set_tenant_session
from evalforge_api.application import evidence_artifact_service, span_service
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from evalforge_api.settings import Settings
from test_evidence_artifact_ingestion import make_artifact_version
from test_run_ingestion import bootstrap_run_tenant, create_run
from test_span_ingestion import span_input
from test_trace_ingestion import make_trace

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]

_TENANT_OWNED_TABLES = (
    "runs",
    "run_tool_versions",
    "traces",
    "spans",
    "run_evidence_artifacts",
    "idempotency_records",
)


async def test_direct_database_access_with_no_tenant_context_exposes_no_rows(
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
        email="iso1@example.com",
    )
    run, _created = await create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    trace, _created = await make_trace(
        context=context, run_id=run.id, ingestion_repositories=ingestion_repositories
    )
    version_id = await make_artifact_version(
        context=context, workspace_id=workspace_id, repositories=evaluation_repositories
    )

    await span_service.ingest_spans(
        context=context,
        trace_id=trace.id,
        spans=(span_input("iso-span"),),
        idempotency_key="iso-spans",
        request_fingerprint="iso-spans-fp",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    await evidence_artifact_service.attach_artifact(
        context=context,
        run_id=run.id,
        trace_id=None,
        artifact_version_id=version_id,
        role="log",
        idempotency_key="iso-attach",
        request_fingerprint="iso-attach-fp",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )

    connection = await asyncpg.connect(dsn=str(test_settings.app_database_url))
    try:
        for table in _TENANT_OWNED_TABLES:
            rows = await connection.fetch(f"SELECT * FROM {table}")  # noqa: S608
            assert rows == [], f"{table} exposed rows with no RLS session context"
    finally:
        await connection.close()


async def test_span_cannot_be_its_own_parent(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
    test_settings: Settings,
) -> None:
    context, trace_id = await _bootstrap_trace(
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="iso2@example.com",
    )
    self_id = uuid4()
    connection = await asyncpg.connect(dsn=str(test_settings.app_database_url))
    try:
        await set_tenant_session(connection, tenant_id=context.tenant_id)
        with pytest.raises(asyncpg.exceptions.RaiseError):
            await connection.execute(
                """
                INSERT INTO spans
                    (id, tenant_id, trace_id, batch_id, parent_span_id, name, span_kind,
                     started_at, created_by)
                VALUES ($1, $2, $3, $4, $1, 'self-parent', 'other', now(), $5)
                """,
                self_id,
                context.tenant_id,
                trace_id,
                uuid4(),
                context.user_id,
            )
    finally:
        await connection.close()


async def test_span_parent_must_belong_to_the_same_trace(
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
        email="iso3@example.com",
    )
    run, _created = await create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    trace_one, _created = await make_trace(
        context=context,
        run_id=run.id,
        ingestion_repositories=ingestion_repositories,
        idempotency_key="trace-one-iso",
    )
    trace_two, _created = await make_trace(
        context=context,
        run_id=run.id,
        ingestion_repositories=ingestion_repositories,
        idempotency_key="trace-two-iso",
    )

    (span_in_trace_one,), _created = await span_service.ingest_spans(
        context=context,
        trace_id=trace_one.id,
        spans=(span_input("root-t1"),),
        idempotency_key="iso-t1-batch",
        request_fingerprint="iso-t1-fp",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )

    connection = await asyncpg.connect(dsn=str(test_settings.app_database_url))
    try:
        await set_tenant_session(connection, tenant_id=context.tenant_id)
        with pytest.raises(asyncpg.exceptions.RaiseError):
            await connection.execute(
                """
                INSERT INTO spans
                    (id, tenant_id, trace_id, batch_id, parent_span_id, name, span_kind,
                     started_at, created_by)
                VALUES ($1, $2, $3, $4, $5, 'cross-trace-child', 'other', now(), $6)
                """,
                uuid4(),
                context.tenant_id,
                trace_two.id,
                uuid4(),
                span_in_trace_one.id,
                context.user_id,
            )
    finally:
        await connection.close()


async def _bootstrap_trace(
    *,
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    slug: str,
    email: str,
) -> tuple[TenantContext, UUID]:
    context, workspace_id = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug=slug,
        email=email,
    )
    run, _created = await create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    trace, _created = await make_trace(
        context=context, run_id=run.id, ingestion_repositories=ingestion_repositories
    )
    return context, trace.id
