from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from evalforge_api.app import create_app
from evalforge_api.ports.connectivity import ConnectivityResult
from evalforge_api.settings import Settings


@dataclass
class _StubCheck:
    name: str
    ok: bool

    async def check(self) -> ConnectivityResult:
        return ConnectivityResult(name=self.name, ok=self.ok, detail=None if self.ok else "stub")


def _client_with_stub_checks(settings: Settings, checks: list[_StubCheck]) -> TestClient:
    app = create_app(settings=settings)
    app.state.connectivity_checks = checks
    return TestClient(app)


def test_readyz_returns_200_when_all_dependencies_ok(test_settings: Settings) -> None:
    checks = [
        _StubCheck("postgres", True),
        _StubCheck("redis", True),
        _StubCheck("object_storage", True),
    ]
    client = _client_with_stub_checks(test_settings, checks)
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert all(dependency["ok"] for dependency in body["dependencies"])


def test_readyz_returns_503_when_a_dependency_fails(test_settings: Settings) -> None:
    checks = [
        _StubCheck("postgres", True),
        _StubCheck("redis", False),
        _StubCheck("object_storage", True),
    ]
    client = _client_with_stub_checks(test_settings, checks)
    response = client.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    redis_result = next(d for d in body["dependencies"] if d["name"] == "redis")
    assert redis_result["ok"] is False
    assert redis_result["detail"] == "stub"
