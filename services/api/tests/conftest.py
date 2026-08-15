from __future__ import annotations

import pytest

from evalforge_api.settings import Settings


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql://evalforge:evalforge@localhost:55432/evalforge_test",
        redis_url="redis://localhost:63790/0",
        object_storage_endpoint_url="http://localhost:9100",
        object_storage_access_key="test-access-key",
        object_storage_secret_key="test-secret-key",
        object_storage_bucket="evalforge-test",
    )
