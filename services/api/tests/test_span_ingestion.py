from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

import pytest

from evalforge_api.application import span_service
from evalforge_api.domain.hashing import hash_canonical_content
from evalforge_api.domain.ingestion import SpanBatchTooLargeError, SpanParentNotFoundError
from evalforge_api.domain.ingestion_enums import SpanKind, SpanStatus
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from evalforge_api.ports.traces import SpanInput
from test_run_ingestion import bootstrap_run_tenant, create_run
from test_trace_ingestion import make_trace

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]


def span_input(
    provider_span_id: str, *, parent: str | None = None, **overrides: object
) -> SpanInput:
    defaults: dict[str, object] = {
        "name": "call",
        "span_kind": SpanKind.LLM_CALL,
        "status": SpanStatus.OK,
        "error_message": None,
        "started_at": datetime.now(UTC),
        "ended_at": None,
        "model_version_id": None,
        "retrieval_config_version_id": None,
        "tool_definition_version_id": None,
        "workflow_version_id": None,
        "attributes": {},
        "input_artifact_version_id": None,
        "output_artifact_version_id": None,
        "token_count_input": None,
        "token_count_output": None,
        "cost_amount": None,
        "cost_currency": None,
    }
    defaults.update(overrides)
    return SpanInput(provider_span_id=provider_span_id, provider_parent_span_id=parent, **defaults)  # type: ignore[arg-type]


async def setup_trace(
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


async def test_valid_parent_child_spans_within_one_batch_are_accepted(
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
        email="span1@example.com",
    )
    records, created = await span_service.ingest_spans(
        context=context,
        trace_id=trace_id,
        spans=(span_input("root"), span_input("child", parent="root")),
        idempotency_key="batch-1",
        request_fingerprint=hash_canonical_content({"k": "batch-1"}),
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    assert created is True
    assert len(records) == 2
    by_provider = {r.provider_span_id: r for r in records}
    assert by_provider["child"].parent_span_id == by_provider["root"].id


async def test_span_referencing_a_prior_batchs_parent_is_accepted(
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
        email="span2@example.com",
    )
    first_batch, _created = await span_service.ingest_spans(
        context=context,
        trace_id=trace_id,
        spans=(span_input("root"),),
        idempotency_key="first-batch",
        request_fingerprint="fp-first",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    second_batch, _created = await span_service.ingest_spans(
        context=context,
        trace_id=trace_id,
        spans=(span_input("child-later", parent="root"),),
        idempotency_key="second-batch",
        request_fingerprint="fp-second",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    assert second_batch[0].parent_span_id == first_batch[0].id


async def test_invalid_parent_reference_is_rejected(
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
        email="span3@example.com",
    )
    with pytest.raises(SpanParentNotFoundError):
        await span_service.ingest_spans(
            context=context,
            trace_id=trace_id,
            spans=(span_input("orphan", parent="does-not-exist"),),
            idempotency_key="bad-parent",
            request_fingerprint="fp-bad-parent",
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
        )


async def test_parent_from_a_different_trace_is_rejected(
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
        email="span4@example.com",
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
        idempotency_key="trace-one",
    )
    trace_two, _created = await make_trace(
        context=context,
        run_id=run.id,
        ingestion_repositories=ingestion_repositories,
        idempotency_key="trace-two",
    )
    await span_service.ingest_spans(
        context=context,
        trace_id=trace_one.id,
        spans=(span_input("root-in-trace-one"),),
        idempotency_key="t1-batch",
        request_fingerprint="fp-t1",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    with pytest.raises(SpanParentNotFoundError):
        await span_service.ingest_spans(
            context=context,
            trace_id=trace_two.id,
            spans=(span_input("child-in-trace-two", parent="root-in-trace-one"),),
            idempotency_key="t2-batch",
            request_fingerprint="fp-t2",
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
        )


async def test_oversized_span_batch_is_rejected(
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
        email="span5@example.com",
    )
    too_many = tuple(span_input(f"span-{i}") for i in range(501))
    with pytest.raises(SpanBatchTooLargeError):
        await span_service.ingest_spans(
            context=context,
            trace_id=trace_id,
            spans=too_many,
            idempotency_key="too-big",
            request_fingerprint="fp-too-big",
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
        )
