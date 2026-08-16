from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import pytest

from evalforge_api.application import span_service, versioned_resource_service
from evalforge_api.application.ingestion_validation import ReferencedArtifactNotFoundError
from evalforge_api.domain.evaluation_enums import ResourceKind
from evalforge_api.domain.ingestion_enums import SpanKind
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from test_run_ingestion import bootstrap_run_tenant, create_run
from test_span_ingestion import setup_trace, span_input
from test_trace_ingestion import make_trace

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]


async def test_span_referencing_cross_tenant_artifact_is_rejected(
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
        email="span6@example.com",
    )
    with pytest.raises(ReferencedArtifactNotFoundError):
        await span_service.ingest_spans(
            context=context,
            trace_id=trace_id,
            spans=(span_input("with-artifact", input_artifact_version_id=uuid4()),),
            idempotency_key="bad-artifact",
            request_fingerprint="fp-bad-artifact",
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
        )


async def test_span_with_valid_tool_definition_version_is_accepted(
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
        email="span7@example.com",
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
    tool_resource = await versioned_resource_service.create_resource(
        context=context,
        workspace_id=workspace_id,
        kind=ResourceKind.TOOL_DEFINITION,
        name="search-tool",
        repositories=evaluation_repositories,
    )
    tool_version = await versioned_resource_service.create_version(
        context=context,
        resource_id=tool_resource.id,
        content={"schema": {}},
        derived_from_version_id=None,
        repositories=evaluation_repositories,
    )
    records, _created = await span_service.ingest_spans(
        context=context,
        trace_id=trace.id,
        spans=(
            span_input(
                "tool-call",
                span_kind=SpanKind.TOOL_CALL,
                tool_definition_version_id=tool_version.id,
            ),
        ),
        idempotency_key="tool-batch",
        request_fingerprint="fp-tool",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    assert records[0].tool_definition_version_id == tool_version.id
