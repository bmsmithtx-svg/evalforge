from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from pathlib import Path
from uuid import UUID

import asyncpg
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from evalforge_api.adapters.postgres_pool import create_pool
from evalforge_api.app import create_app
from evalforge_api.dependency_wiring import build_identity_repositories
from evalforge_api.ports.identity import IdentityRepositories
from evalforge_api.settings import Settings

API_DIR = Path(__file__).resolve().parents[1]

TEST_JWT_SIGNING_KEY = "evalforge-test-suite-signing-key-do-not-use-in-production-0001"
TEST_APP_DB_CREDENTIAL = "evalforge-test-app-role-password-0001"
TEST_APP_DATABASE_URL = (
    f"postgresql://evalforge_app:{TEST_APP_DB_CREDENTIAL}@localhost:55432/evalforge_test"
)


def _build_test_settings() -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql://evalforge:evalforge-test@localhost:55432/evalforge_test",
        app_database_url=TEST_APP_DATABASE_URL,
        redis_url="redis://localhost:63790/0",
        object_storage_endpoint_url="http://localhost:9100",
        object_storage_access_key="test-access-key",
        object_storage_secret_key="test-secret-key",
        object_storage_bucket="evalforge-test",
        jwt_signing_key=TEST_JWT_SIGNING_KEY,
    )


@pytest.fixture
def test_settings() -> Settings:
    return _build_test_settings()


@pytest.fixture(scope="session")
def test_settings_session() -> Settings:
    return _build_test_settings()


def _settings_env(settings: Settings) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "EVALFORGE_ENVIRONMENT": settings.environment,
            "EVALFORGE_DATABASE_URL": str(settings.database_url),
            "EVALFORGE_APP_DATABASE_URL": str(settings.app_database_url),
            "EVALFORGE_APP_DB_PASSWORD": TEST_APP_DB_CREDENTIAL,
            "EVALFORGE_REDIS_URL": str(settings.redis_url),
            "EVALFORGE_OBJECT_STORAGE_ENDPOINT_URL": settings.object_storage_endpoint_url,
            "EVALFORGE_OBJECT_STORAGE_ACCESS_KEY": settings.object_storage_access_key,
            "EVALFORGE_OBJECT_STORAGE_SECRET_KEY": settings.object_storage_secret_key,
            "EVALFORGE_OBJECT_STORAGE_BUCKET": settings.object_storage_bucket,
            "EVALFORGE_JWT_SIGNING_KEY": settings.jwt_signing_key,
        }
    )
    return env


@pytest.fixture(scope="session", autouse=True)
def _migrated_test_database(test_settings_session: Settings) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        env=_settings_env(test_settings_session),
        check=True,
        capture_output=True,
        text=True,
    )


async def _truncate_identity_tables(dsn: str) -> None:
    connection = await asyncpg.connect(dsn=dsn)
    try:
        await connection.execute(
            "TRUNCATE TABLE tenant_memberships, tenants, users RESTART IDENTITY CASCADE"
        )
    finally:
        await connection.close()


@pytest.fixture(autouse=True)
def _reset_identity_tables(_migrated_test_database: None, test_settings_session: Settings) -> None:
    asyncio.run(_truncate_identity_tables(str(test_settings_session.database_url)))


@pytest_asyncio.fixture
async def identity_repositories(test_settings: Settings) -> AsyncIterator[IdentityRepositories]:
    pool = await create_pool(str(test_settings.app_database_url))
    yield build_identity_repositories(pool)
    await pool.close()


@pytest.fixture
def api_client(test_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings=test_settings)) as client:
        yield client


@pytest.fixture
def create_tenant(test_settings: Settings) -> Callable[..., Awaitable[UUID]]:
    """Create a tenant using the administrative DSN.

    Tenant creation is intentionally not exposed through the API or the
    least-privilege application role in Milestone 3 (see the identity
    migration's grants), so tests set up tenant fixtures directly.
    """

    async def _create(slug: str, name: str = "Test Tenant") -> UUID:
        connection = await asyncpg.connect(dsn=str(test_settings.database_url))
        try:
            row = await connection.fetchrow(
                "INSERT INTO tenants (slug, name) VALUES ($1, $2) RETURNING id", slug, name
            )
        finally:
            await connection.close()
        assert row is not None
        return UUID(str(row["id"]))

    return _create
