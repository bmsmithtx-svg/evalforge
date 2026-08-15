from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import jwt
from fastapi.testclient import TestClient

from evalforge_api.settings import Settings

_STRONG_PASSPHRASE = "Correct-Horse-Battery-Staple-9"
_WRONG_PASSPHRASE = "an-incorrect-passphrase-value"


def _register(
    client: TestClient, email: str, passphrase: str = _STRONG_PASSPHRASE
) -> dict[str, object]:
    response = client.post("/auth/register", json={"email": email, "password": passphrase})
    assert response.status_code == 201, response.text
    return dict(response.json())


def test_register_creates_an_active_user(api_client: TestClient) -> None:
    body = _register(api_client, "new-user@example.com")
    assert body["email"] == "new-user@example.com"
    assert body["status"] == "active"
    assert "id" in body


def test_register_rejects_duplicate_email(api_client: TestClient) -> None:
    _register(api_client, "dup@example.com")
    response = api_client.post(
        "/auth/register", json={"email": "dup@example.com", "password": _STRONG_PASSPHRASE}
    )
    assert response.status_code == 409


def test_register_rejects_weak_password(api_client: TestClient) -> None:
    response = api_client.post(
        "/auth/register", json={"email": "weak@example.com", "password": "short"}
    )
    assert response.status_code == 422


def test_register_rejects_malformed_email(api_client: TestClient) -> None:
    response = api_client.post(
        "/auth/register", json={"email": "not-an-email", "password": _STRONG_PASSPHRASE}
    )
    assert response.status_code == 422


def test_login_returns_bearer_token_for_correct_credentials(api_client: TestClient) -> None:
    _register(api_client, "login-ok@example.com")
    response = api_client.post(
        "/auth/login", json={"email": "login-ok@example.com", "password": _STRONG_PASSPHRASE}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_login_rejects_wrong_password(api_client: TestClient) -> None:
    _register(api_client, "login-bad@example.com")
    response = api_client.post(
        "/auth/login", json={"email": "login-bad@example.com", "password": _WRONG_PASSPHRASE}
    )
    assert response.status_code == 401


def test_login_rejects_unknown_email(api_client: TestClient) -> None:
    response = api_client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": _STRONG_PASSPHRASE}
    )
    assert response.status_code == 401


async def test_login_rejects_disabled_account(
    api_client: TestClient, test_settings: Settings
) -> None:
    body = _register(api_client, "disabled@example.com")
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        await connection.execute(
            "UPDATE users SET status = 'disabled' WHERE id = $1", UUID(str(body["id"]))
        )
    finally:
        await connection.close()

    response = api_client.post(
        "/auth/login", json={"email": "disabled@example.com", "password": _STRONG_PASSPHRASE}
    )
    assert response.status_code == 401


def test_me_requires_credentials(api_client: TestClient) -> None:
    response = api_client.get("/auth/me")
    assert response.status_code == 401


def test_me_rejects_malformed_bearer_token(api_client: TestClient) -> None:
    response = api_client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_me_returns_the_authenticated_principal(api_client: TestClient) -> None:
    _register(api_client, "me@example.com")
    login = api_client.post(
        "/auth/login", json={"email": "me@example.com", "password": _STRONG_PASSPHRASE}
    )
    token = login.json()["access_token"]

    response = api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


def test_me_rejects_expired_token(api_client: TestClient, test_settings: Settings) -> None:
    _register(api_client, "expired@example.com")
    now = datetime.now(UTC)
    expired_payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "email": "expired@example.com",
        "iss": test_settings.jwt_issuer,
        "aud": test_settings.jwt_audience,
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
    }
    expired_token = jwt.encode(expired_payload, test_settings.jwt_signing_key, algorithm="HS256")

    response = api_client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})

    assert response.status_code == 401
