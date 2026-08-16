"""Idempotent artifact-upload orchestration for Milestone 5 ingestion.

Wraps Milestone 4's ``artifact_service.create_artifact`` and
``store_artifact_version`` (reused unchanged — see docs/ARCHITECTURE.md,
"do not bypass" the Milestone 4 artifact boundary) with the same
durable idempotency-record mechanism ingestion writes use elsewhere.

Because artifact upload has a genuine external side effect (an S3 PUT)
that cannot be wrapped in the same PostgreSQL transaction as the
idempotency-record insert, this is a best-effort guarantee rather than
the fully atomic one ``adapters.idempotency_sql.with_idempotency``
gives pure-database writes: on a lost race between two concurrent
requests carrying the same key, both may store bytes, but only the
winning artifact version is ever recorded in ``idempotency_records`` or
returned to any caller — see the Milestone 5 completion report's
idempotency-semantics section for the full argument.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

from evalforge_api.adapters.idempotency_sql import find_idempotency_record, record_idempotency_key
from evalforge_api.adapters.rls_session import set_tenant_session
from evalforge_api.application import artifact_service
from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.ingestion import IdempotencyConflictError, PayloadTooLargeError
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.artifacts import ArtifactVersionRecord
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories

_INGEST_ARTIFACT_OPERATION = "ingest_artifact"


async def upload_artifact(
    *,
    context: TenantContext,
    workspace_id: UUID | None,
    media_type: str,
    purpose: str,
    body: bytes,
    max_bytes: int,
    idempotency_key: str,
    request_fingerprint: str,
    repositories: EvaluationRepositories,
    db_pool: asyncpg.Pool,
) -> tuple[ArtifactVersionRecord, bool]:
    if len(body) > max_bytes:
        raise PayloadTooLargeError(
            f"Artifact exceeds the {max_bytes}-byte limit ({len(body)} bytes)."
        )

    async with db_pool.acquire() as connection, connection.transaction():
        await set_tenant_session(connection, tenant_id=context.tenant_id)
        existing = await find_idempotency_record(
            connection,
            tenant_id=context.tenant_id,
            operation=_INGEST_ARTIFACT_OPERATION,
            idempotency_key=idempotency_key,
        )
    if existing is not None:
        if existing.request_fingerprint != request_fingerprint:
            raise IdempotencyConflictError(idempotency_key)
        version = await repositories.artifacts.get_artifact_version(
            tenant_id=context.tenant_id, version_id=existing.resource_id
        )
        assert version is not None
        return version, False

    # create_artifact/store_artifact_version already enforce
    # TenantAction.CREATE_ARTIFACT and emit their own audit events
    # (Milestone 4); this wrapper does not duplicate that check.
    artifact = await artifact_service.create_artifact(
        context=context,
        workspace_id=workspace_id,
        media_type=media_type,
        purpose=purpose,
        repositories=repositories,
    )
    version = await artifact_service.store_artifact_version(
        context=context,
        artifact_id=artifact.id,
        body=body,
        content_type=media_type,
        derived_from_artifact_version_id=None,
        repositories=repositories,
    )

    try:
        async with db_pool.acquire() as connection, connection.transaction():
            await set_tenant_session(connection, tenant_id=context.tenant_id)
            await record_idempotency_key(
                connection,
                tenant_id=context.tenant_id,
                operation=_INGEST_ARTIFACT_OPERATION,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                resource_type="artifact_version",
                resource_id=version.id,
                created_by=context.user_id,
            )
    except asyncpg.exceptions.UniqueViolationError:
        return await _replay_after_lost_race(
            context=context,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            repositories=repositories,
            db_pool=db_pool,
        )

    emit_audit_event(
        event="artifact_ingestion",
        outcome="success",
        actor_user_id=str(context.user_id),
        tenant_id=str(context.tenant_id),
        artifact_id=str(artifact.id),
        version_id=str(version.id),
    )
    return version, True


async def _replay_after_lost_race(
    *,
    context: TenantContext,
    idempotency_key: str,
    request_fingerprint: str,
    repositories: EvaluationRepositories,
    db_pool: asyncpg.Pool,
) -> tuple[ArtifactVersionRecord, bool]:
    async with db_pool.acquire() as connection, connection.transaction():
        await set_tenant_session(connection, tenant_id=context.tenant_id)
        winner = await find_idempotency_record(
            connection,
            tenant_id=context.tenant_id,
            operation=_INGEST_ARTIFACT_OPERATION,
            idempotency_key=idempotency_key,
        )
    assert winner is not None
    if winner.request_fingerprint != request_fingerprint:
        raise IdempotencyConflictError(idempotency_key)
    version = await repositories.artifacts.get_artifact_version(
        tenant_id=context.tenant_id, version_id=winner.resource_id
    )
    assert version is not None
    return version, False
