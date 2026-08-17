"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from evalforge_api.adapters.postgres_pool import create_pool
from evalforge_api.dependency_wiring import (
    build_connectivity_checks,
    build_evaluation_repositories,
    build_identity_repositories,
    build_ingestion_repositories,
)
from evalforge_api.error_handling import register_error_handlers
from evalforge_api.logging_setup import configure_logging, get_logger
from evalforge_api.middleware.rate_limit import RateLimitMiddleware
from evalforge_api.middleware.request_size_limit import RequestSizeLimitMiddleware
from evalforge_api.routes import (
    auth,
    dataset_import_export,
    dataset_operations,
    dataset_snapshots,
    datasets,
    health,
    ingestion_artifacts,
    ingestion_runs,
    ingestion_spans,
    ingestion_traces,
    readiness,
    tenants,
    test_cases,
)
from evalforge_api.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured FastAPI application."""
    settings = settings or get_settings()
    configure_logging(settings)
    logger = get_logger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.connectivity_checks = build_connectivity_checks(settings)
        pool = await create_pool(str(settings.app_database_url))
        app.state.db_pool = pool
        app.state.identity_repositories = build_identity_repositories(pool)
        app.state.evaluation_repositories = build_evaluation_repositories(pool, settings)
        app.state.ingestion_repositories = build_ingestion_repositories(pool)
        logger.info("evalforge_api_startup", environment=settings.environment)
        yield
        await pool.close()
        logger.info("evalforge_api_shutdown")

    app = FastAPI(
        title="EvalForge API",
        version="0.5.0",
        description=(
            "EvalForge control/API service — authentication, tenant isolation, the versioned "
            "evaluation domain, and SDK/API run, trace, and artifact ingestion."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        RateLimitMiddleware,
        max_requests=settings.rate_limit_requests_per_window,
        window_seconds=settings.rate_limit_window_seconds,
        exempt_paths=frozenset({"/healthz"}),
    )
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_body_bytes=settings.max_request_body_bytes,
        path_suffix_overrides={"/artifacts": settings.max_artifact_bytes},
    )
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_allowed_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_error_handlers(app)

    # Routes depend on get_settings via FastAPI's Depends() so they can
    # be unit-tested without touching process-wide state. Overriding it
    # here ensures every route sees the same settings instance this
    # factory was built with, rather than the separately cached,
    # environment-sourced get_settings() singleton.
    app.dependency_overrides[get_settings] = lambda: settings

    app.include_router(health.router)
    app.include_router(readiness.router)
    app.include_router(auth.router)
    app.include_router(tenants.router)
    app.include_router(ingestion_runs.router)
    app.include_router(ingestion_traces.router)
    app.include_router(ingestion_spans.router)
    app.include_router(ingestion_artifacts.router)
    app.include_router(datasets.router)
    app.include_router(test_cases.router)
    app.include_router(dataset_snapshots.router)
    app.include_router(dataset_import_export.router)
    app.include_router(dataset_operations.router)

    return app
