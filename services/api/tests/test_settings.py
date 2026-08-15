from __future__ import annotations

import pytest
from pydantic import ValidationError

from evalforge_api.settings import Settings


def test_missing_database_url_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVALFORGE_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(
            redis_url="redis://localhost:6379/0",
            object_storage_endpoint_url="http://localhost:9000",
            object_storage_access_key="key",
            object_storage_secret_key="secret",
            object_storage_bucket="bucket",
            _env_file=None,  # type: ignore[call-arg]
        )


@pytest.mark.parametrize("placeholder", ["changeme", "CHANGEME", "placeholder", ""])
def test_placeholder_secret_fails_closed(placeholder: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql://user:pass@localhost:5432/db",
            redis_url="redis://localhost:6379/0",
            object_storage_endpoint_url="http://localhost:9000",
            object_storage_access_key=placeholder,
            object_storage_secret_key="secret",
            object_storage_bucket="bucket",
            _env_file=None,  # type: ignore[call-arg]
        )


def test_valid_settings_construct(test_settings: Settings) -> None:
    assert test_settings.environment == "test"
    assert test_settings.is_production is False
