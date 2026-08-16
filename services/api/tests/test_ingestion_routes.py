from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from evalforge_api.application import workspace_service
from evalforge_api.domain.enums import TenantRole, UserKind
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.identity import IdentityRepositories
from evalforge_api.security.passwords import hash_password

CreateTenant = Callable[..., Awaitable[UUID]]
BuildContext = Callable[..., TenantContext]
_PASSPHRASE = "Ingestion-Route-Test-Passphrase-1"


async def _create_member(
    repositories: IdentityRepositories, *, email: str, tenant_id: UUID, role: TenantRole
) -> UUID:
    user = await repositories.users.create(
        email=email, password_hash=hash_password(_PASSPHRASE), kind=UserKind.HUMAN
    )
    await repositories.memberships.create(user_id=user.id, tenant_id=tenant_id, role=role)
    return user.id


def _login(client: TestClient, email: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": _PASSPHRASE})
    assert response.status_code == 200, response.text
    token: str = response.json()["access_token"]
    return token


def _auth(token: str, *, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


async def _setup_developer(
    *,
    identity_repositories: IdentityRepositories,
    evaluation_repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
    slug: str,
    email: str,
) -> tuple[UUID, UUID]:
    tenant_id = await create_tenant(slug)
    user_id = await _create_member(
        identity_repositories, email=email, tenant_id=tenant_id, role=TenantRole.DEVELOPER
    )
    admin_context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.TENANT_ADMIN
    )
    workspace = await workspace_service.create_workspace(
        context=admin_context, slug="ws", name="Workspace", repositories=evaluation_repositories
    )
    return tenant_id, workspace.id


def _run_body(workspace_id: UUID) -> dict[str, object]:
    return {
        "workspace_id": str(workspace_id),
        "source": "pytest-api",
        "started_at": datetime.now(UTC).isoformat(),
        "metadata": {"case": "api"},
    }


def test_unauthenticated_run_creation_is_denied(api_client: TestClient) -> None:
    response = api_client.post(
        f"/tenants/{uuid4()}/runs",
        json=_run_body(uuid4()),
        headers={"Idempotency-Key": "no-auth"},
    )
    assert response.status_code == 401


async def test_reviewer_cannot_ingest_a_run_via_api(
    api_client: TestClient,
    identity_repositories: IdentityRepositories,
    evaluation_repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
) -> None:
    tenant_id = await create_tenant("tenant-reviewer")
    admin_id = await _create_member(
        identity_repositories,
        email="admin-r@example.com",
        tenant_id=tenant_id,
        role=TenantRole.TENANT_ADMIN,
    )
    await _create_member(
        identity_repositories,
        email="reviewer-r@example.com",
        tenant_id=tenant_id,
        role=TenantRole.REVIEWER,
    )
    admin_context = build_tenant_context(
        tenant_id=tenant_id, user_id=admin_id, role=TenantRole.TENANT_ADMIN
    )
    workspace = await workspace_service.create_workspace(
        context=admin_context, slug="ws", name="Workspace", repositories=evaluation_repositories
    )
    token = _login(api_client, "reviewer-r@example.com")

    response = api_client.post(
        f"/tenants/{tenant_id}/runs",
        json=_run_body(workspace.id),
        headers=_auth(token, idempotency_key="denied-key"),
    )
    assert response.status_code == 403


async def test_run_creation_requires_idempotency_key_header(
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
        slug="tenant-no-key",
        email="dev-nokey@example.com",
    )
    token = _login(api_client, "dev-nokey@example.com")

    response = api_client.post(
        f"/tenants/{tenant_id}/runs", json=_run_body(workspace_id), headers=_auth(token)
    )
    assert response.status_code == 422


async def test_create_run_via_api_is_idempotent(
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
        slug="tenant-idem",
        email="dev-idem@example.com",
    )
    token = _login(api_client, "dev-idem@example.com")
    body = _run_body(workspace_id)

    first = api_client.post(
        f"/tenants/{tenant_id}/runs", json=body, headers=_auth(token, idempotency_key="api-key-1")
    )
    second = api_client.post(
        f"/tenants/{tenant_id}/runs", json=body, headers=_auth(token, idempotency_key="api-key-1")
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


async def test_run_trace_span_ingestion_end_to_end(
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
        slug="tenant-e2e",
        email="dev-e2e@example.com",
    )
    token = _login(api_client, "dev-e2e@example.com")

    run_response = api_client.post(
        f"/tenants/{tenant_id}/runs",
        json=_run_body(workspace_id),
        headers=_auth(token, idempotency_key="e2e-run"),
    )
    assert run_response.status_code == 201
    run_id = run_response.json()["id"]

    trace_response = api_client.post(
        f"/tenants/{tenant_id}/traces",
        json={"run_id": run_id, "source": "pytest-api", "metadata": {}},
        headers=_auth(token, idempotency_key="e2e-trace"),
    )
    assert trace_response.status_code == 201
    trace_id = trace_response.json()["id"]
    assert trace_response.json()["workspace_id"] == str(workspace_id)

    span_response = api_client.post(
        f"/tenants/{tenant_id}/traces/{trace_id}/spans",
        json={
            "spans": [
                {
                    "span_id": "root",
                    "name": "llm-call",
                    "span_kind": "llm_call",
                    "started_at": datetime.now(UTC).isoformat(),
                }
            ]
        },
        headers=_auth(token, idempotency_key="e2e-spans"),
    )
    assert span_response.status_code == 200, span_response.text
    assert len(span_response.json()) == 1

    finalize_trace = api_client.post(
        f"/tenants/{tenant_id}/traces/{trace_id}/finalize",
        json={},
        headers=_auth(token, idempotency_key="e2e-finalize-trace"),
    )
    assert finalize_trace.status_code == 200
    assert finalize_trace.json()["status"] == "finalized"

    finalize_run = api_client.post(
        f"/tenants/{tenant_id}/runs/{run_id}/finalize",
        json={"status": "completed", "ended_at": datetime.now(UTC).isoformat()},
        headers=_auth(token, idempotency_key="e2e-finalize-run"),
    )
    assert finalize_run.status_code == 200
    assert finalize_run.json()["status"] == "completed"

    get_run = api_client.get(f"/tenants/{tenant_id}/runs/{run_id}", headers=_auth(token))
    assert get_run.status_code == 200


async def test_cross_tenant_run_lookup_returns_not_found(
    api_client: TestClient,
    identity_repositories: IdentityRepositories,
    evaluation_repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
) -> None:
    tenant_a, workspace_a = await _setup_developer(
        identity_repositories=identity_repositories,
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        slug="tenant-xa",
        email="dev-xa@example.com",
    )
    tenant_b, workspace_b = await _setup_developer(
        identity_repositories=identity_repositories,
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        slug="tenant-xb",
        email="dev-xb@example.com",
    )
    token_b = _login(api_client, "dev-xb@example.com")
    run_b = api_client.post(
        f"/tenants/{tenant_b}/runs",
        json=_run_body(workspace_b),
        headers=_auth(token_b, idempotency_key="xb-run"),
    )
    assert run_b.status_code == 201

    token_a = _login(api_client, "dev-xa@example.com")
    del workspace_a
    cross_tenant_get = api_client.get(
        f"/tenants/{tenant_a}/runs/{run_b.json()['id']}", headers=_auth(token_a)
    )
    assert cross_tenant_get.status_code == 404


def test_openapi_includes_ingestion_routes(api_client: TestClient) -> None:
    response = api_client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/tenants/{tenant_id}/runs" in paths
    assert "/tenants/{tenant_id}/traces" in paths
    assert "/tenants/{tenant_id}/traces/{trace_id}/spans" in paths
    assert "/tenants/{tenant_id}/artifacts" in paths
