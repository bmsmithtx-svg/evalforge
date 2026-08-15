"""Typed, fail-closed application settings.

Every field with no default is required. Construction raises
``pydantic.ValidationError`` when a required or malformed value is present,
so the process never starts serving traffic on incomplete or invalid
sensitive configuration.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "ci", "staging", "production"]

_PLACEHOLDER_VALUES = {"", "changeme", "change-me", "placeholder", "todo", "xxx"}


class Settings(BaseSettings):
    """Process-wide configuration loaded from environment variables.

    All variables use the ``EVALFORGE_`` prefix (for example
    ``EVALFORGE_DATABASE_URL``). Sensitive values have no default so a
    missing or placeholder value fails process startup instead of
    silently running with an insecure default.
    """

    model_config = SettingsConfigDict(
        env_prefix="EVALFORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    environment: Environment = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    host: str = "0.0.0.0"  # noqa: S104 -- binds inside a container; not exposed directly
    port: int = Field(default=8000, ge=1, le=65535)

    # Administrative DSN used only for migrations and readiness checks.
    database_url: PostgresDsn

    # Least-privilege DSN the running application uses for every
    # request-serving query. A distinct, non-superuser role from
    # `database_url` so PostgreSQL row-level security on tenant-owned
    # tables actually applies — table owners and superusers bypass RLS
    # regardless of policy definitions.
    app_database_url: PostgresDsn

    redis_url: RedisDsn

    object_storage_endpoint_url: str
    object_storage_access_key: str
    object_storage_secret_key: str
    object_storage_bucket: str
    object_storage_region: str = "us-east-1"
    object_storage_use_tls: bool = True

    cors_allowed_origins: tuple[str, ...] = ()

    max_request_body_bytes: int = Field(default=2_000_000, gt=0)
    rate_limit_requests_per_window: int = Field(default=60, gt=0)
    rate_limit_window_seconds: float = Field(default=60.0, gt=0)

    readiness_timeout_seconds: float = Field(default=2.0, gt=0)

    jwt_signing_key: str = Field(min_length=32)
    jwt_issuer: str = "evalforge"
    jwt_audience: str = "evalforge-api"
    jwt_access_token_ttl_seconds: int = Field(default=900, gt=0)

    @field_validator(
        "object_storage_endpoint_url",
        "object_storage_access_key",
        "object_storage_secret_key",
        "object_storage_bucket",
        "jwt_signing_key",
    )
    @classmethod
    def _reject_placeholder_secrets(cls, value: str, info: object) -> str:
        if value.strip().lower() in _PLACEHOLDER_VALUES:
            field_name = getattr(info, "field_name", "value")
            raise ValueError(f"{field_name} must not be a placeholder value")
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so configuration is validated exactly once per process; a
    failure here must prevent the application factory from completing.
    """
    return Settings()  # type: ignore[call-arg]
