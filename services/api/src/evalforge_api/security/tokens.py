"""Access-token issuance and verification.

Tokens are opaque bearer credentials to every other module: only this
file knows the signing algorithm, issuer, audience, and claim shape.
Verification always checks signature, issuer, audience, and expiry —
never just the payload — so a malformed or forged token is rejected
before any claim is trusted.

Tokens intentionally carry only the subject and email. Status and role
are looked up fresh from the database on every request (see
``evalforge_api.security.dependencies``) so a disabled account or
changed membership takes effect immediately instead of staying valid
until token expiry.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from evalforge_api.settings import Settings

_ALGORITHM = "HS256"


class TokenValidationError(Exception):
    """Raised for any missing, malformed, expired, or forged token."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class TokenClaims:
    user_id: UUID
    email: str


def issue_access_token(*, user_id: UUID, email: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(seconds=settings.jwt_access_token_ttl_seconds),
    }
    return jwt.encode(payload, settings.jwt_signing_key, algorithm=_ALGORITHM)


def verify_access_token(token: str, *, settings: Settings) -> TokenClaims:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_signing_key,
            algorithms=[_ALGORITHM],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp", "iat", "sub", "aud", "iss", "email"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenValidationError("expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenValidationError("invalid") from exc

    try:
        user_id = UUID(str(payload["sub"]))
    except (ValueError, TypeError) as exc:
        raise TokenValidationError("malformed_subject") from exc

    return TokenClaims(user_id=user_id, email=str(payload["email"]))
