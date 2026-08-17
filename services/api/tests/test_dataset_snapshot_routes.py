"""HTTP surface for test cases and dataset snapshots: version
history, draft membership, finalization, comparison, and the 409
a finalized snapshot returns for any further membership change.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

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


async def test_test_case_and_snapshot_flow_over_http(
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
        slug="tenant-snapshot",
        email="engineer-snapshot@example.com",
    )
    token = _login(api_client, "engineer-snapshot@example.com")
    dataset_id = api_client.post(
        f"/tenants/{tenant_id}/datasets",
        json={"workspace_id": str(workspace_id), "name": "Snapshot flow"},
        headers=_auth(token),
    ).json()["id"]

    created = api_client.post(
        f"/tenants/{tenant_id}/datasets/{dataset_id}/test-cases",
        json={"external_key": "case-1", "content": {"input": "first question"}},
        headers=_auth(token),
    )
    assert created.status_code == 200, created.text
    test_case_id = created.json()["test_case"]["id"]
    first_version_id = created.json()["version"]["id"]
    assert created.json()["version"]["version_number"] == 1
    assert created.json()["version"]["dedup_hash"]

    revised = api_client.post(
        f"/tenants/{tenant_id}/test-cases/{test_case_id}/versions",
        json={"content": {"input": "revised question"}},
        headers=_auth(token),
    )
    assert revised.status_code == 200
    assert revised.json()["version_number"] == 2

    history = api_client.get(
        f"/tenants/{tenant_id}/test-cases/{test_case_id}/versions", headers=_auth(token)
    )
    assert [item["version_number"] for item in history.json()["versions"]] == [1, 2]

    # Build two snapshots and compare them.
    first_snapshot = api_client.post(
        f"/tenants/{tenant_id}/datasets/{dataset_id}/snapshots", headers=_auth(token)
    ).json()["id"]
    assert (
        api_client.post(
            f"/tenants/{tenant_id}/snapshots/{first_snapshot}/items",
            json={"test_case_version_id": first_version_id, "sequence_index": 0},
            headers=_auth(token),
        ).status_code
        == 201
    )
    finalized = api_client.post(
        f"/tenants/{tenant_id}/snapshots/{first_snapshot}/finalize", headers=_auth(token)
    )
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "finalized"
    assert finalized.json()["content_hash"]

    second_snapshot = api_client.post(
        f"/tenants/{tenant_id}/datasets/{dataset_id}/snapshots", headers=_auth(token)
    ).json()["id"]
    api_client.post(
        f"/tenants/{tenant_id}/snapshots/{second_snapshot}/items",
        json={"test_case_version_id": revised.json()["id"], "sequence_index": 0},
        headers=_auth(token),
    )
    api_client.post(
        f"/tenants/{tenant_id}/snapshots/{second_snapshot}/finalize", headers=_auth(token)
    )

    comparison = api_client.get(
        f"/tenants/{tenant_id}/snapshot-comparisons",
        params={"left_snapshot_id": first_snapshot, "right_snapshot_id": second_snapshot},
        headers=_auth(token),
    )
    assert comparison.status_code == 200, comparison.text
    assert comparison.json()["changed"] == [
        {
            "test_case_id": test_case_id,
            "left_version_number": 1,
            "right_version_number": 2,
        }
    ]

    # A finalized snapshot rejects further membership: HTTP 409.
    conflict = api_client.post(
        f"/tenants/{tenant_id}/snapshots/{first_snapshot}/items",
        json={"test_case_version_id": revised.json()["id"], "sequence_index": 1},
        headers=_auth(token),
    )
    assert conflict.status_code == 409

    listed = api_client.get(
        f"/tenants/{tenant_id}/datasets/{dataset_id}/snapshots", headers=_auth(token)
    )
    assert len(listed.json()["snapshots"]) == 2

    items = api_client.get(
        f"/tenants/{tenant_id}/snapshots/{first_snapshot}/items", headers=_auth(token)
    )
    assert [item["test_case_version_id"] for item in items.json()["items"]] == [first_version_id]
