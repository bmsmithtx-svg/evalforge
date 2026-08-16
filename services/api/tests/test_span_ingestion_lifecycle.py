from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

import asyncpg
import pytest

from evalforge_api.application import span_service, trace_service
from evalforge_api.domain.ingestion import IdempotencyConflictError, ImmutableTraceError
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from evalforge_api.settings import Settings
from test_span_ingestion import setup_trace, span_input

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]


async def test_ingest_spans_same_key_same_payload_is_idempotent(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
    test_settings: Settings,
) -> None:
    context, trace_id = await setup_trace(
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="lc1@example.com",
    )
    first, first_created = await span_service.ingest_spans(
        context=context,
        trace_id=trace_id,
        spans=(span_input("a"), span_input("b", parent="a")),
        idempotency_key="fixed-batch-key",
        request_fingerprint="fixed-fp",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    second, second_created = await span_service.ingest_spans(
        context=context,
        trace_id=trace_id,
        spans=(span_input("a"), span_input("b", parent="a")),
        idempotency_key="fixed-batch-key",
        request_fingerprint="fixed-fp",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    assert first_created is True
    assert second_created is False
    assert {r.id for r in first} == {r.id for r in second}

    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        count = await connection.fetchval(
            "SELECT count(*) FROM spans WHERE trace_id = $1", trace_id
        )
    finally:
        await connection.close()
    assert count == 2


async def test_ingest_spans_same_key_different_payload_conflicts(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context, trace_id = await setup_trace(
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="lc2@example.com",
    )
    await span_service.ingest_spans(
        context=context,
        trace_id=trace_id,
        spans=(span_input("a"),),
        idempotency_key="conflict-batch",
        request_fingerprint="fp-1",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    with pytest.raises(IdempotencyConflictError):
        await span_service.ingest_spans(
            context=context,
            trace_id=trace_id,
            spans=(span_input("a"),),
            idempotency_key="conflict-batch",
            request_fingerprint="fp-2",
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
        )


async def test_finalized_trace_rejects_new_span_batches(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context, trace_id = await setup_trace(
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="lc3@example.com",
    )
    await trace_service.finalize_trace(
        context=context,
        trace_id=trace_id,
        started_at=None,
        ended_at=None,
        idempotency_key="finalize-before-span",
        request_fingerprint="fp-finalize",
        ingestion_repositories=ingestion_repositories,
    )
    with pytest.raises(ImmutableTraceError):
        await span_service.ingest_spans(
            context=context,
            trace_id=trace_id,
            spans=(span_input("too-late"),),
            idempotency_key="too-late-batch",
            request_fingerprint="fp-too-late",
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
        )


async def test_list_spans_returns_ingested_spans(
    evaluation_repositories: EvaluationRepositories,
    ingestion_repositories: IngestionRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    context, trace_id = await setup_trace(
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-a",
        email="lc4@example.com",
    )
    await span_service.ingest_spans(
        context=context,
        trace_id=trace_id,
        spans=(span_input("a"), span_input("b", parent="a")),
        idempotency_key="list-batch",
        request_fingerprint="fp-list",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    listed = await span_service.list_spans(
        context=context, trace_id=trace_id, ingestion_repositories=ingestion_repositories
    )
    assert {s.provider_span_id for s in listed} == {"a", "b"}
