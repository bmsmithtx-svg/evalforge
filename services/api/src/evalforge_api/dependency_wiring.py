"""Wires concrete adapters into the ports the routes depend on.

This is the single place that knows about concrete PostgreSQL, Redis,
and object-storage clients. Routes and other application code depend
only on the port protocols in ``evalforge_api.ports``.
"""

from __future__ import annotations

import asyncpg

from evalforge_api.adapters.membership_repository import PostgresMembershipRepository
from evalforge_api.adapters.object_storage import ObjectStorageConnectivityCheck
from evalforge_api.adapters.postgres import PostgresConnectivityCheck
from evalforge_api.adapters.redis_cache import RedisConnectivityCheck
from evalforge_api.adapters.tenant_repository import PostgresTenantRepository
from evalforge_api.adapters.user_repository import PostgresUserRepository
from evalforge_api.ports.connectivity import ConnectivityCheck
from evalforge_api.ports.identity import IdentityRepositories
from evalforge_api.settings import Settings


def build_identity_repositories(pool: asyncpg.Pool) -> IdentityRepositories:
    return IdentityRepositories(
        users=PostgresUserRepository(pool),
        tenants=PostgresTenantRepository(pool),
        memberships=PostgresMembershipRepository(pool),
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
