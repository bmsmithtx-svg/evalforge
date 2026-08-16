from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from evalforge_api.application import run_service
from evalforge_api.application.run_service import RunNotFoundError
from evalforge_api.domain.enums import TenantRole
from evalforge_api.domain.ingestion import IdempotencyConflictError, ImmutableRunError
from evalforge_api.domain.ingestion_enums import RunStatus
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from evalforge_api.settings import Settings
from test_run_ingestion import bootstrap_run_tenant, create_run

CreateTenant = Callable[..., Awaitable[UUID]]
CreateUser = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]


async def test_create_run_same_key_same_payload_is_idempotent(
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
        email="idem@example.com",
    )
    first, first_created = await create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
        idempotency_key="fixed-key",
    )
    second, second_created = await create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
        idempotency_key="fixed-key",
    )
    assert first_created is True
    assert second_created is False
    assert first.id == second.id

    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        count = await connection.fetchval(
            "SELECT count(*) FROM runs WHERE tenant_id = $1", context.tenant_id
        )
    finally:
        await connection.close()
    assert count == 1


async def test_create_run_same_key_different_payload_conflicts(
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
        email="conflict@example.com",
    )
    await create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
        idempotency_key="conflict-key",
        request_fingerprint="fingerprint-one",
    )
    with pytest.raises(IdempotencyConflictError):
        await create_run(
            context=context,
            workspace_id=workspace_id,
            evaluation_repositories=evaluation_repositories,
            ingestion_repositories=ingestion_repositories,
            idempotency_key="conflict-key",
            request_fingerprint="fingerprint-two",
        )


async def test_finalize_run_transitions_to_terminal(
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
        email="finalize@example.com",
    )
    run, _created = await create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    finalized, created = await run_service.finalize_run(
        context=context,
        run_id=run.id,
        status=RunStatus.COMPLETED,
        ended_at=datetime.now(UTC),
        metadata=None,
        idempotency_key="finalize-key",
        request_fingerprint="finalize-fp",
        ingestion_repositories=ingestion_repositories,
    )
    assert created is True
    assert finalized.status == RunStatus.COMPLETED
    assert finalized.finalized_at is not None


async def test_finalized_run_cannot_be_finalized_again_with_a_different_request(
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
        email="immutable@example.com",
    )
    run, _created = await create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    await run_service.finalize_run(
        context=context,
        run_id=run.id,
        status=RunStatus.COMPLETED,
        ended_at=datetime.now(UTC),
        metadata=None,
        idempotency_key="first-finalize",
        request_fingerprint="fp-1",
        ingestion_repositories=ingestion_repositories,
    )
    with pytest.raises(ImmutableRunError):
        await run_service.finalize_run(
            context=context,
            run_id=run.id,
            status=RunStatus.FAILED,
            ended_at=datetime.now(UTC),
            metadata=None,
            idempotency_key="second-finalize",
            request_fingerprint="fp-2",
            ingestion_repositories=ingestion_repositories,
        )


async def test_finalize_replays_with_same_key_and_payload(
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
        email="replay@example.com",
    )
    run, _created = await create_run(
        context=context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )
    ended_at = datetime.now(UTC)
    first, first_created = await run_service.finalize_run(
        context=context,
        run_id=run.id,
        status=RunStatus.COMPLETED,
        ended_at=ended_at,
        metadata=None,
        idempotency_key="replay-key",
        request_fingerprint="replay-fp",
        ingestion_repositories=ingestion_repositories,
    )
    second, second_created = await run_service.finalize_run(
        context=context,
        run_id=run.id,
        status=RunStatus.COMPLETED,
        ended_at=ended_at,
        metadata=None,
        idempotency_key="replay-key",
        request_fingerprint="replay-fp",
        ingestion_repositories=ingestion_repositories,
    )
    assert first_created is True
    assert second_created is False
    assert first.status == second.status == RunStatus.COMPLETED


async def test_view_run_requires_authorization_and_returns_not_found_for_unknown_id(
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
        email="viewer@example.com",
        role=TenantRole.READ_ONLY_OBSERVER,
    )
    admin_context = build_tenant_context(
        tenant_id=context.tenant_id, user_id=context.user_id, role=TenantRole.TENANT_ADMIN
    )
    run, _created = await create_run(
        context=admin_context,
        workspace_id=workspace_id,
        evaluation_repositories=evaluation_repositories,
        ingestion_repositories=ingestion_repositories,
    )

    viewed = await run_service.get_run(
        context=context, run_id=run.id, ingestion_repositories=ingestion_repositories
    )
    assert viewed.id == run.id

    with pytest.raises(RunNotFoundError):
        await run_service.get_run(
            context=context, run_id=uuid4(), ingestion_repositories=ingestion_repositories
        )
