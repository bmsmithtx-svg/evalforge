from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from evalforge_api.security.tokens import (
    TokenValidationError,
    issue_access_token,
    verify_access_token,
)
from evalforge_api.settings import Settings


def test_verify_access_token_accepts_a_freshly_issued_token(test_settings: Settings) -> None:
    user_id = uuid4()
    token = issue_access_token(user_id=user_id, email="dev@example.com", settings=test_settings)

    claims = verify_access_token(token, settings=test_settings)

    assert claims.user_id == user_id
    assert claims.email == "dev@example.com"


def test_verify_access_token_rejects_malformed_token(test_settings: Settings) -> None:
    with pytest.raises(TokenValidationError):
        verify_access_token("not-a-jwt", settings=test_settings)


def test_verify_access_token_rejects_wrong_signing_key(test_settings: Settings) -> None:
    token = issue_access_token(user_id=uuid4(), email="dev@example.com", settings=test_settings)
    forged_settings = test_settings.model_copy(
        update={"jwt_signing_key": "a-completely-different-signing-key-value"}
    )

    with pytest.raises(TokenValidationError):
        verify_access_token(token, settings=forged_settings)


def test_verify_access_token_rejects_wrong_audience(test_settings: Settings) -> None:
    token = issue_access_token(user_id=uuid4(), email="dev@example.com", settings=test_settings)
    mismatched_settings = test_settings.model_copy(update={"jwt_audience": "some-other-audience"})

    with pytest.raises(TokenValidationError):
        verify_access_token(token, settings=mismatched_settings)


def test_verify_access_token_rejects_wrong_issuer(test_settings: Settings) -> None:
    token = issue_access_token(user_id=uuid4(), email="dev@example.com", settings=test_settings)
    mismatched_settings = test_settings.model_copy(update={"jwt_issuer": "some-other-issuer"})

    with pytest.raises(TokenValidationError):
        verify_access_token(token, settings=mismatched_settings)


def test_verify_access_token_rejects_expired_token(test_settings: Settings) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid4()),
        "email": "dev@example.com",
        "iss": test_settings.jwt_issuer,
        "aud": test_settings.jwt_audience,
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
    }
    expired_token = jwt.encode(payload, test_settings.jwt_signing_key, algorithm="HS256")

    with pytest.raises(TokenValidationError):
        verify_access_token(expired_token, settings=test_settings)


def test_verify_access_token_rejects_unsigned_none_algorithm_token(test_settings: Settings) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid4()),
        "email": "dev@example.com",
        "iss": test_settings.jwt_issuer,
        "aud": test_settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    forged_token = jwt.encode(payload, "", algorithm="none")

    with pytest.raises(TokenValidationError):
        verify_access_token(forged_token, settings=test_settings)
