from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest

from evalforge_api.application import artifact_service, evidence_artifact_service
from evalforge_api.application.evidence_artifact_service import InvalidEvidenceOwnerError
from evalforge_api.application.ingestion_validation import ReferencedArtifactNotFoundError
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from test_run_ingestion import bootstrap_run_tenant, create_run
from test_trace_ingestion import make_trace

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]


async def make_artifact_version(
    *, context: TenantContext, workspace_id: UUID, repositories: EvaluationRepositories
) -> UUID:
    artifact = await artifact_service.create_artifact(
        context=context,
        workspace_id=workspace_id,
        media_type="text/plain",
        purpose="evidence",
        repositories=repositories,
    )
    version = await artifact_service.store_artifact_version(
        context=context,
        artifact_id=artifact.id,
        body=b"evidence-bytes",
        content_type="text/plain",
        derived_from_artifact_version_id=None,
        repositories=repositories,
    )
    return version.id


async def test_attach_artifact_to_run(
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
        email="ev1@example.com",
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
    record, created = await evidence_artifact_service.attach_artifact(
        context=context,
        run_id=run.id,
        trace_id=None,
        artifact_version_id=version_id,
        role="log",
        idempotency_key="attach-run",
        request_fingerprint="fp-attach-run",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    assert created is True
    assert record.run_id == run.id
    assert record.artifact_version_id == version_id


async def test_attach_artifact_to_trace(
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
        email="ev2@example.com",
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
    record, created = await evidence_artifact_service.attach_artifact(
        context=context,
        run_id=None,
        trace_id=trace.id,
        artifact_version_id=version_id,
        role="rendered_prompt",
        idempotency_key="attach-trace",
        request_fingerprint="fp-attach-trace",
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    assert created is True
    assert record.trace_id == trace.id


async def test_attach_requires_exactly_one_owner(
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
        email="ev3@example.com",
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
    with pytest.raises(InvalidEvidenceOwnerError):
        await evidence_artifact_service.attach_artifact(
            context=context,
            run_id=None,
            trace_id=None,
            artifact_version_id=version_id,
            role="x",
            idempotency_key="neither",
            request_fingerprint="fp-neither",
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
        )
    with pytest.raises(InvalidEvidenceOwnerError):
        await evidence_artifact_service.attach_artifact(
            context=context,
            run_id=run.id,
            trace_id=trace.id,
            artifact_version_id=version_id,
            role="x",
            idempotency_key="both",
            request_fingerprint="fp-both",
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
        )


async def test_cross_tenant_artifact_reference_is_rejected(
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
        email="ev4a@example.com",
    )
    context_b, workspace_b = await bootstrap_run_tenant(
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        create_user=create_user,
        slug="tenant-b",
        email="ev4b@example.com",
    )
    run_a, _created = await create_run(
        context=context_a,
        workspace_id=workspace_a,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    version_b = await make_artifact_version(
        context=context_b, workspace_id=workspace_b, repositories=evaluation_repositories
    )
    with pytest.raises(ReferencedArtifactNotFoundError):
        await evidence_artifact_service.attach_artifact(
            context=context_a,
            run_id=run_a.id,
            trace_id=None,
            artifact_version_id=version_b,
            role="log",
            idempotency_key="cross-tenant",
            request_fingerprint="fp-cross-tenant",
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
        )
