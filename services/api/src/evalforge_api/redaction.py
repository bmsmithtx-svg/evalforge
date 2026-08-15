"""Sensitive-field redaction for structured log events.

Centralizing redaction here means every log call site — current and
future — is protected by the same denylist instead of relying on each
call site to remember not to log secrets.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

REDACTED_PLACEHOLDER = "***REDACTED***"

_SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "authorization",
    "cookie",
    "session",
    "credential",
    "dsn",
    "connection_string",
    "database_url",
    "redis_url",
)


def is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower()
    return any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS)


def redact_event(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """A structlog processor that redacts sensitive top-level keys.

    Applied to every log event before rendering, regardless of which
    module emitted it.
    """
    for key in list(event_dict.keys()):
        if is_sensitive_key(key):
            event_dict[key] = REDACTED_PLACEHOLDER
    return event_dict
