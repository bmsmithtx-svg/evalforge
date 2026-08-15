"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from evalforge_api.dependency_wiring import build_connectivity_checks
from evalforge_api.error_handling import register_error_handlers
from evalforge_api.logging_setup import configure_logging, get_logger
from evalforge_api.middleware.rate_limit import RateLimitMiddleware
from evalforge_api.middleware.request_size_limit import RequestSizeLimitMiddleware
from evalforge_api.routes import health, readiness
from evalforge_api.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured FastAPI application.

    Milestone 2 scope: foundation-level health, readiness, and metadata
    only. No product-domain routes are registered here.
    """
    settings = settings or get_settings()
    configure_logging(settings)
    logger = get_logger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.connectivity_checks = build_connectivity_checks(settings)
        logger.info("evalforge_api_startup", environment=settings.environment)
        yield
        logger.info("evalforge_api_shutdown")

    app = FastAPI(
        title="EvalForge API",
        version="0.2.0",
        description="EvalForge control/API service. Milestone 2 engineering foundation.",
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

    app.include_router(health.router)
    app.include_router(readiness.router)

    return app
