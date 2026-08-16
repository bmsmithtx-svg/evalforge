"""SDK exception hierarchy.

Every non-2xx API response and every transport failure is translated
into one of these typed exceptions rather than leaking httpx's own
exception types to SDK callers.
"""

from __future__ import annotations


class EvalForgeSDKError(Exception):
    """Base class for every exception this SDK raises."""


class EvalForgeConnectionError(EvalForgeSDKError):
    """The request could not reach the EvalForge API at all."""


class EvalForgeTimeoutError(EvalForgeSDKError):
    """The request exceeded the configured timeout."""


class EvalForgeAPIError(EvalForgeSDKError):
    """The API returned a non-2xx response with a standardized error
    body (``evalforge_api.error_handling``)."""

    def __init__(self, *, status_code: int, code: str, message: str, error_id: str | None) -> None:
        super().__init__(f"[{status_code} {code}] {message}")
        self.status_code = status_code
        self.code = code
        self.message = message
        self.error_id = error_id
