"""Wires concrete adapters into the ports the routes depend on.

This is the single place that knows about concrete PostgreSQL, Redis,
and object-storage clients. Routes and other application code depend
only on the port protocols in ``evalforge_api.ports``.
"""

from __future__ import annotations

import asyncpg

from evalforge_api.adapters.artifact_object_storage import S3ArtifactObjectStorage
from evalforge_api.adapters.artifact_repository import PostgresArtifactRepository
from evalforge_api.adapters.dataset_repository import PostgresDatasetRepository
from evalforge_api.adapters.dataset_snapshot_repository import PostgresDatasetSnapshotRepository
from evalforge_api.adapters.evidence_artifact_repository import (
    PostgresEvidenceArtifactRepository,
)
from evalforge_api.adapters.membership_repository import PostgresMembershipRepository
from evalforge_api.adapters.object_storage import ObjectStorageConnectivityCheck
from evalforge_api.adapters.postgres import PostgresConnectivityCheck
from evalforge_api.adapters.redis_cache import RedisConnectivityCheck
from evalforge_api.adapters.run_repository import PostgresRunRepository
from evalforge_api.adapters.span_repository import PostgresSpanRepository
from evalforge_api.adapters.tenant_repository import PostgresTenantRepository
from evalforge_api.adapters.trace_repository import PostgresTraceRepository
from evalforge_api.adapters.user_repository import PostgresUserRepository
from evalforge_api.adapters.versioned_resource_repository import (
    PostgresVersionedResourceRepository,
)
from evalforge_api.adapters.workspace_repository import (
    PostgresEvaluationTargetRepository,
    PostgresWorkspaceRepository,
)
from evalforge_api.ports.connectivity import ConnectivityCheck
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.identity import IdentityRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from evalforge_api.settings import Settings


def build_identity_repositories(pool: asyncpg.Pool) -> IdentityRepositories:
    return IdentityRepositories(
        users=PostgresUserRepository(pool),
        tenants=PostgresTenantRepository(pool),
        memberships=PostgresMembershipRepository(pool),
    )


def build_evaluation_repositories(pool: asyncpg.Pool, settings: Settings) -> EvaluationRepositories:
    return EvaluationRepositories(
        workspaces=PostgresWorkspaceRepository(pool),
        evaluation_targets=PostgresEvaluationTargetRepository(pool),
        versioned_resources=PostgresVersionedResourceRepository(pool),
        datasets=PostgresDatasetRepository(pool),
        snapshots=PostgresDatasetSnapshotRepository(pool),
        artifacts=PostgresArtifactRepository(pool),
        artifact_storage=S3ArtifactObjectStorage(
            endpoint_url=settings.object_storage_endpoint_url,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
            bucket=settings.object_storage_bucket,
            region=settings.object_storage_region,
        ),
    )


def build_ingestion_repositories(pool: asyncpg.Pool) -> IngestionRepositories:
    return IngestionRepositories(
        runs=PostgresRunRepository(pool),
        traces=PostgresTraceRepository(pool),
        spans=PostgresSpanRepository(pool),
        evidence_artifacts=PostgresEvidenceArtifactRepository(pool),
    )


def build_connectivity_checks(settings: Settings) -> list[ConnectivityCheck]:
    return [
        PostgresConnectivityCheck(
            dsn=str(settings.database_url),
            timeout_seconds=settings.readiness_timeout_seconds,
        ),
        RedisConnectivityCheck(
            url=str(settings.redis_url),
            timeout_seconds=settings.readiness_timeout_seconds,
        ),
        ObjectStorageConnectivityCheck(
            endpoint_url=settings.object_storage_endpoint_url,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
            bucket=settings.object_storage_bucket,
            region=settings.object_storage_region,
            timeout_seconds=settings.readiness_timeout_seconds,
        ),
    ]
