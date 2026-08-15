"""Structured logging configuration with sensitive-field redaction."""

from __future__ import annotations

import logging
import sys

import structlog

from evalforge_api.redaction import redact_event
from evalforge_api.settings import Settings


def configure_logging(settings: Settings) -> None:
    """Configure process-wide structured logging.

    Must run once during application startup, before any other module
    logs, so every log event is redacted and consistently formatted.
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.log_level,
    )

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if settings.environment != "local"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_event,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[settings.log_level]
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
