from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.identity import IdentityRepositories
from test_ingestion_routes import _auth, _login, _setup_developer

CreateTenant = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]


async def test_artifact_upload_via_api(
    api_client: TestClient,
    identity_repositories: IdentityRepositories,
    evaluation_repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
) -> None:
    tenant_id, workspace_id = await _setup_developer(
        identity_repositories=identity_repositories,
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        slug="tenant-upload",
        email="dev-upload@example.com",
    )
    token = _login(api_client, "dev-upload@example.com")
    body = b"hello ingestion artifact bytes"

    response = api_client.post(
        f"/tenants/{tenant_id}/artifacts",
        headers=_auth(token, idempotency_key="upload-1"),
        data={"purpose": "log", "workspace_id": str(workspace_id)},
        files={"file": ("evidence.txt", body, "text/plain")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["byte_size"] == len(body)
    assert payload["evidence_attached"] is False


async def test_artifact_upload_attaches_to_run_when_run_id_given(
    api_client: TestClient,
    identity_repositories: IdentityRepositories,
    evaluation_repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
) -> None:
    tenant_id, workspace_id = await _setup_developer(
        identity_repositories=identity_repositories,
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        slug="tenant-attach",
        email="dev-attach@example.com",
    )
    token = _login(api_client, "dev-attach@example.com")
    run_response = api_client.post(
        f"/tenants/{tenant_id}/runs",
        json={
            "workspace_id": str(workspace_id),
            "source": "pytest-api",
            "started_at": "2026-08-15T00:00:00+00:00",
            "metadata": {},
        },
        headers=_auth(token, idempotency_key="attach-run"),
    )
    assert run_response.status_code == 201
    run_id = run_response.json()["id"]

    response = api_client.post(
        f"/tenants/{tenant_id}/artifacts",
        headers=_auth(token, idempotency_key="attach-upload"),
        data={"purpose": "log", "workspace_id": str(workspace_id), "run_id": run_id},
        files={"file": ("evidence.txt", b"attached bytes", "text/plain")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["evidence_attached"] is True


def test_unauthenticated_artifact_upload_is_denied(api_client: TestClient) -> None:
    response = api_client.post(
        f"/tenants/{uuid4()}/artifacts",
        headers={"Idempotency-Key": "no-auth-upload"},
        data={"purpose": "log"},
        files={"file": ("evidence.txt", b"bytes", "text/plain")},
    )
    assert response.status_code == 401
