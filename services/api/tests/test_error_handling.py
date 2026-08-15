from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient

from evalforge_api.app import create_app
from evalforge_api.settings import Settings


def test_not_found_returns_standard_envelope(test_settings: Settings) -> None:
    client = TestClient(create_app(settings=test_settings))
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert "error_id" in body["error"]


def test_unhandled_exception_returns_standard_envelope_without_leaking_detail(
    test_settings: Settings,
) -> None:
    app = create_app(settings=test_settings)

    @app.get("/boom")
    async def _boom() -> None:
        raise RuntimeError("sensitive internal detail: connection string leaked")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "sensitive internal detail" not in response.text


def test_validation_error_from_a_custom_validator_serializes_safely(
    test_settings: Settings,
) -> None:
    """Regression test: a field_validator raising ValueError used to
    crash response rendering because RequestValidationError.errors()
    embeds the raw exception under ctx.error, which plain json.dumps
    cannot serialize."""
    passphrase = "irrelevant-registration-value"

    with TestClient(create_app(settings=test_settings)) as client:
        response = client.post(
            "/auth/register", json={"email": "not-an-email", "password": passphrase}
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_explicit_http_exception_uses_standard_envelope(test_settings: Settings) -> None:
    app = create_app(settings=test_settings)

    @app.get("/forbidden-thing")
    async def _forbidden() -> None:
        raise HTTPException(status_code=403, detail="not allowed")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/forbidden-thing")

    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "forbidden"
    assert body["error"]["message"] == "not allowed"
