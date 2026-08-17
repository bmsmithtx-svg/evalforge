"""HTTP surface for dataset lifecycle: authentication,
authorization, create/read/update/archive, validation errors, and
audit emission.

Snapshot endpoints are covered by
``test_dataset_snapshot_routes.py`` and the bulk operations by
``test_dataset_operation_routes.py``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
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
_PASSPHRASE = "Dataset-Route-Test-Passphrase-1"


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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _setup_tenant(
    *,
    identity_repositories: IdentityRepositories,
    evaluation_repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
    slug: str,
    email: str,
    role: TenantRole = TenantRole.EVALUATION_ENGINEER,
) -> tuple[UUID, UUID]:
    tenant_id = await create_tenant(slug)
    admin_id = await _create_member(
        identity_repositories,
        email=f"admin-{slug}@example.com",
        tenant_id=tenant_id,
        role=TenantRole.TENANT_ADMIN,
    )
    await _create_member(identity_repositories, email=email, tenant_id=tenant_id, role=role)
    admin_context = build_tenant_context(
        tenant_id=tenant_id, user_id=admin_id, role=TenantRole.TENANT_ADMIN
    )
    workspace = await workspace_service.create_workspace(
        context=admin_context, slug="ws", name="Workspace", repositories=evaluation_repositories
    )
    return tenant_id, workspace.id


def test_unauthenticated_dataset_creation_is_denied(api_client: TestClient) -> None:
    response = api_client.post(
        f"/tenants/{uuid4()}/datasets", json={"workspace_id": str(uuid4()), "name": "X"}
    )
    assert response.status_code == 401


def test_unauthenticated_dataset_listing_is_denied(api_client: TestClient) -> None:
    assert api_client.get(f"/tenants/{uuid4()}/datasets").status_code == 401


async def test_reviewer_cannot_create_or_mutate_a_dataset_via_api(
    api_client: TestClient,
    identity_repositories: IdentityRepositories,
    evaluation_repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
) -> None:
    tenant_id, workspace_id = await _setup_tenant(
        identity_repositories=identity_repositories,
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        slug="tenant-reviewer",
        email="reviewer@example.com",
        role=TenantRole.REVIEWER,
    )
    token = _login(api_client, "reviewer@example.com")

    created = api_client.post(
        f"/tenants/{tenant_id}/datasets",
        json={"workspace_id": str(workspace_id), "name": "Denied"},
        headers=_auth(token),
    )
    assert created.status_code == 403
    assert created.json()["error"]["code"] == "forbidden"

    # A reviewer may still read.
    listed = api_client.get(f"/tenants/{tenant_id}/datasets", headers=_auth(token))
    assert listed.status_code == 200
    assert listed.json()["datasets"] == []


async def test_full_dataset_lifecycle_over_http(
    api_client: TestClient,
    identity_repositories: IdentityRepositories,
    evaluation_repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
) -> None:
    tenant_id, workspace_id = await _setup_tenant(
        identity_repositories=identity_repositories,
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        slug="tenant-lifecycle",
        email="engineer-lifecycle@example.com",
    )
    token = _login(api_client, "engineer-lifecycle@example.com")

    created = api_client.post(
        f"/tenants/{tenant_id}/datasets",
        json={
            "workspace_id": str(workspace_id),
            "name": "Support QA",
            "description": "Tier-1",
            "tags": ["support"],
            "metadata": {"owner": "quality"},
        },
        headers=_auth(token),
    )
    assert created.status_code == 201, created.text
    dataset_id = created.json()["id"]
    assert created.json()["source"] == "manual"

    fetched = api_client.get(f"/tenants/{tenant_id}/datasets/{dataset_id}", headers=_auth(token))
    assert fetched.status_code == 200
    assert fetched.json()["tags"] == ["support"]

    updated = api_client.patch(
        f"/tenants/{tenant_id}/datasets/{dataset_id}",
        json={"name": "Support QA v2"},
        headers=_auth(token),
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Support QA v2"
    assert updated.json()["description"] == "Tier-1"

    archived = api_client.post(
        f"/tenants/{tenant_id}/datasets/{dataset_id}/archive", headers=_auth(token)
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["archived_at"] is not None


async def test_invalid_test_case_content_is_rejected_with_422(
    api_client: TestClient,
    identity_repositories: IdentityRepositories,
    evaluation_repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
) -> None:
    tenant_id, workspace_id = await _setup_tenant(
        identity_repositories=identity_repositories,
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        slug="tenant-invalid",
        email="engineer-invalid@example.com",
    )
    token = _login(api_client, "engineer-invalid@example.com")
    dataset_id = api_client.post(
        f"/tenants/{tenant_id}/datasets",
        json={"workspace_id": str(workspace_id), "name": "Invalid"},
        headers=_auth(token),
    ).json()["id"]

    response = api_client.post(
        f"/tenants/{tenant_id}/datasets/{dataset_id}/test-cases",
        json={"content": {"expected_output": "no input at all"}},
        headers=_auth(token),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_dataset_mutation_emits_an_audit_event(
    api_client: TestClient,
    identity_repositories: IdentityRepositories,
    evaluation_repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
    capsys,  # noqa: ANN001 -- pytest's built-in capture fixture
) -> None:
    """Audit events reach the configured structlog output; the test
    suite renders logs to stdout, so capturing stdout is enough."""
    tenant_id, workspace_id = await _setup_tenant(
        identity_repositories=identity_repositories,
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        slug="tenant-audit",
        email="engineer-audit@example.com",
    )
    token = _login(api_client, "engineer-audit@example.com")
    capsys.readouterr()

    dataset_id = api_client.post(
        f"/tenants/{tenant_id}/datasets",
        json={"workspace_id": str(workspace_id), "name": "Audited"},
        headers=_auth(token),
    ).json()["id"]
    api_client.patch(
        f"/tenants/{tenant_id}/datasets/{dataset_id}",
        json={"name": "Audited v2"},
        headers=_auth(token),
    )
    api_client.post(f"/tenants/{tenant_id}/datasets/{dataset_id}/archive", headers=_auth(token))

    captured = capsys.readouterr().out
    assert "dataset_creation" in captured
    assert "dataset_update" in captured
    assert "dataset_archival" in captured
    assert str(tenant_id) in captured
