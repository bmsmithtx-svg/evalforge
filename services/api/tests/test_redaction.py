from __future__ import annotations

from evalforge_api.redaction import REDACTED_PLACEHOLDER, is_sensitive_key, redact_event


def test_is_sensitive_key_matches_known_fragments() -> None:
    assert is_sensitive_key("password")
    assert is_sensitive_key("Object_Storage_Secret_Key")
    assert is_sensitive_key("Authorization")
    assert not is_sensitive_key("tenant_id")


def test_redact_event_masks_sensitive_top_level_keys() -> None:
    event = {"message": "startup", "provider_api_key": "sk-live-example", "count": 3}
    redacted = redact_event(None, "info", event)
    assert redacted["provider_api_key"] == REDACTED_PLACEHOLDER
    assert redacted["message"] == "startup"
    assert redacted["count"] == 3
