"""Structured audit-event emission.

Milestone 2's redaction processor already scrubs sensitive keys from
every structured log event, so audit events emitted through this
module inherit that protection automatically. This is the single call
site application services use to record authentication, authorization,
and membership-relevant events — call sites should not build their own
ad hoc audit log lines.
"""

from __future__ import annotations

from typing import Any

import structlog

_audit_logger = structlog.get_logger("evalforge_api.audit")


def emit_audit_event(
    *,
    event: str,
    outcome: str,
    actor_user_id: str | None = None,
    tenant_id: str | None = None,
    **extra: Any,
) -> None:
    _audit_logger.info(
        "audit_event",
        audit_event_type=event,
        outcome=outcome,
        actor_user_id=actor_user_id,
        tenant_id=tenant_id,
        **extra,
    )
