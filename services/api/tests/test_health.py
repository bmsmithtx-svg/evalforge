from __future__ import annotations

from fastapi.testclient import TestClient

from evalforge_api.app import create_app
from evalforge_api.settings import Settings


def test_healthz_returns_ok(test_settings: Settings) -> None:
    client = TestClient(create_app(settings=test_settings))
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
