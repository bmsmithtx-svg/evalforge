from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import asyncpg
import pytest

from evalforge_api.application import trace_service
from evalforge_api.application.trace_service import TraceNotFoundError
from evalforge_api.domain.ingestion import IdempotencyConflictError, ImmutableTraceError
from evalforge_api.domain.ingestion_enums import TraceStatus
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from evalforge_api.settings import Settings
from test_run_ingestion import bootstrap_run_tenant, create_run
from test_trace_ingestion import make_trace

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]


async def _setup_run_and_trace(
    *,
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    slug: str,
    email: str,
) -> tuple[TenantContext, object]:
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
    return context, trace


async def test_create_trace_same_key_same_payload_is_idempotent(
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
        email="tidem@example.com",
    )
    run, _created = await create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    first, first_created = await make_trace(
        context=context,
        run_id=run.id,
        ingestion_repositories=ingestion_repositories,
        idempotency_key="fixed-trace-key",
    )
    second, second_created = await make_trace(
        context=context,
        run_id=run.id,
        ingestion_repositories=ingestion_repositories,
        idempotency_key="fixed-trace-key",
    )
    assert first_created is True
    assert second_created is False
    assert first.id == second.id

    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        count = await connection.fetchval(
            "SELECT count(*) FROM traces WHERE tenant_id = $1", context.tenant_id
        )
    finally:
        await connection.close()
    assert count == 1


async def test_create_trace_same_key_different_payload_conflicts(
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
        email="tconflict@example.com",
    )
    run, _created = await create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    await make_trace(
        context=context,
        run_id=run.id,
        ingestion_repositories=ingestion_repositories,
        idempotency_key="trace-conflict-key",
        request_fingerprint="fp-one",
    )
    with pytest.raises(IdempotencyConflictError):
        await make_trace(
            context=context,
            run_id=run.id,
            ingestion_repositories=ingestion_repositories,
            idempotency_key="trace-conflict-key",
            request_fingerprint="fp-two",
        )


async def test_finalize_trace_and_immutability(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context, trace = await _setup_run_and_trace(
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="tfinalize@example.com",
    )
    finalized, created = await trace_service.finalize_trace(
        context=context,
        trace_id=trace.id,
        started_at=None,
        ended_at=None,
        idempotency_key="finalize-trace-1",
        request_fingerprint="finalize-trace-fp-1",
        ingestion_repositories=ingestion_repositories,
    )
    assert created is True
    assert finalized.status == TraceStatus.FINALIZED

    with pytest.raises(ImmutableTraceError):
        await trace_service.finalize_trace(
            context=context,
            trace_id=trace.id,
            started_at=None,
            ended_at=None,
            idempotency_key="finalize-trace-2",
            request_fingerprint="finalize-trace-fp-2",
            ingestion_repositories=ingestion_repositories,
        )


async def test_finalize_trace_replays_with_same_key_and_payload(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context, trace = await _setup_run_and_trace(
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="treplay@example.com",
    )
    first, first_created = await trace_service.finalize_trace(
        context=context,
        trace_id=trace.id,
        started_at=None,
        ended_at=None,
        idempotency_key="replay-key",
        request_fingerprint="replay-fp",
        ingestion_repositories=ingestion_repositories,
    )
    second, second_created = await trace_service.finalize_trace(
        context=context,
        trace_id=trace.id,
        started_at=None,
        ended_at=None,
        idempotency_key="replay-key",
        request_fingerprint="replay-fp",
        ingestion_repositories=ingestion_repositories,
    )
    assert first_created is True
    assert second_created is False
    assert first.status == second.status == TraceStatus.FINALIZED


async def test_view_trace_returns_not_found_for_unknown_id(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context, trace = await _setup_run_and_trace(
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="tview@example.com",
    )
    viewed = await trace_service.get_trace(
        context=context, trace_id=trace.id, ingestion_repositories=ingestion_repositories
    )
    assert viewed.id == trace.id

    with pytest.raises(TraceNotFoundError):
        await trace_service.get_trace(
            context=context, trace_id=uuid4(), ingestion_repositories=ingestion_repositories
        )
