from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from evalforge_api.app import create_app
from evalforge_api.domain.enums import TenantRole, UserKind
from evalforge_api.ports.identity import IdentityRepositories
from evalforge_api.security.passwords import hash_password
from evalforge_api.settings import Settings

CreateTenant = Callable[..., Awaitable[UUID]]
_PASSPHRASE = "Cross-Tenant-Test-Passphrase-1"


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


async def test_tenant_admin_can_view_own_context_and_members(
    api_client: TestClient, identity_repositories: IdentityRepositories, create_tenant: CreateTenant
) -> None:
    tenant_a = await create_tenant("tenant-a")
    await _create_member(
        identity_repositories,
        email="admin-a@example.com",
        tenant_id=tenant_a,
        role=TenantRole.TENANT_ADMIN,
    )
    token = _login(api_client, "admin-a@example.com")

    context = api_client.get(f"/tenants/{tenant_a}/context", headers=_auth(token))
    assert context.status_code == 200
    assert context.json()["role"] == "tenant_admin"

    members = api_client.get(f"/tenants/{tenant_a}/members", headers=_auth(token))
    assert members.status_code == 200
    assert len(members.json()) == 1


async def test_tenant_a_user_cannot_view_tenant_b_context(
    api_client: TestClient, identity_repositories: IdentityRepositories, create_tenant: CreateTenant
) -> None:
    tenant_a = await create_tenant("tenant-a")
    tenant_b = await create_tenant("tenant-b")
    await _create_member(
        identity_repositories,
        email="only-a@example.com",
        tenant_id=tenant_a,
        role=TenantRole.TENANT_ADMIN,
    )
    token = _login(api_client, "only-a@example.com")

    response = api_client.get(f"/tenants/{tenant_b}/context", headers=_auth(token))

    assert response.status_code == 403
    assert "tenant-b" not in response.text


async def test_substituting_tenant_b_id_does_not_bypass_authorization(
    api_client: TestClient, identity_repositories: IdentityRepositories, create_tenant: CreateTenant
) -> None:
    tenant_a = await create_tenant("tenant-a")
    tenant_b = await create_tenant("tenant-b")
    await _create_member(
        identity_repositories,
        email="member-a@example.com",
        tenant_id=tenant_a,
        role=TenantRole.DEVELOPER,
    )
    await _create_member(
        identity_repositories,
        email="admin-b@example.com",
        tenant_id=tenant_b,
        role=TenantRole.TENANT_ADMIN,
    )
    token = _login(api_client, "member-a@example.com")

    response = api_client.get(f"/tenants/{tenant_b}/members", headers=_auth(token))

    assert response.status_code == 403


async def test_role_in_one_tenant_does_not_confer_the_same_role_in_another(
    api_client: TestClient, identity_repositories: IdentityRepositories, create_tenant: CreateTenant
) -> None:
    tenant_a = await create_tenant("tenant-a")
    tenant_b = await create_tenant("tenant-b")
    user = await identity_repositories.users.create(
        email="multi@example.com", password_hash=hash_password(_PASSPHRASE), kind=UserKind.HUMAN
    )
    await identity_repositories.memberships.create(
        user_id=user.id, tenant_id=tenant_a, role=TenantRole.TENANT_ADMIN
    )
    await identity_repositories.memberships.create(
        user_id=user.id, tenant_id=tenant_b, role=TenantRole.READ_ONLY_OBSERVER
    )
    token = _login(api_client, "multi@example.com")

    context_a = api_client.get(f"/tenants/{tenant_a}/context", headers=_auth(token))
    context_b = api_client.get(f"/tenants/{tenant_b}/context", headers=_auth(token))
    assert context_a.json()["role"] == "tenant_admin"
    assert context_b.json()["role"] == "read_only_observer"

    members_a = api_client.get(f"/tenants/{tenant_a}/members", headers=_auth(token))
    members_b = api_client.get(f"/tenants/{tenant_b}/members", headers=_auth(token))
    assert members_a.status_code == 200
    assert members_b.status_code == 403

    my_tenants = api_client.get("/tenants", headers=_auth(token))
    assert {row["tenant_id"] for row in my_tenants.json()} == {str(tenant_a), str(tenant_b)}


async def test_members_listing_excludes_other_tenants_users(
    api_client: TestClient, identity_repositories: IdentityRepositories, create_tenant: CreateTenant
) -> None:
    tenant_a = await create_tenant("tenant-a")
    tenant_b = await create_tenant("tenant-b")
    admin_a = await _create_member(
        identity_repositories,
        email="admin-a2@example.com",
        tenant_id=tenant_a,
        role=TenantRole.TENANT_ADMIN,
    )
    await _create_member(
        identity_repositories,
        email="admin-b2@example.com",
        tenant_id=tenant_b,
        role=TenantRole.TENANT_ADMIN,
    )
    token = _login(api_client, "admin-a2@example.com")

    response = api_client.get(f"/tenants/{tenant_a}/members", headers=_auth(token))

    member_ids = {member["user_id"] for member in response.json()}
    assert member_ids == {str(admin_a)}


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
async def test_concurrent_requests_from_different_tenants_do_not_leak_context(
    test_settings: Settings,
    identity_repositories: IdentityRepositories,
    create_tenant: CreateTenant,
) -> None:
    tenant_a = await create_tenant("tenant-a")
    tenant_b = await create_tenant("tenant-b")
    await _create_member(
        identity_repositories,
        email="conc-a@example.com",
        tenant_id=tenant_a,
        role=TenantRole.TENANT_ADMIN,
    )
    await _create_member(
        identity_repositories,
        email="conc-b@example.com",
        tenant_id=tenant_b,
        role=TenantRole.DEVELOPER,
    )

    app = create_app(settings=test_settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            login_a = await client.post(
                "/auth/login", json={"email": "conc-a@example.com", "password": _PASSPHRASE}
            )
            login_b = await client.post(
                "/auth/login", json={"email": "conc-b@example.com", "password": _PASSPHRASE}
            )
            token_a = login_a.json()["access_token"]
            token_b = login_b.json()["access_token"]

            async def _fetch(token: str, tenant_id: UUID) -> httpx.Response:
                return await client.get(f"/tenants/{tenant_id}/context", headers=_auth(token))

            requests = [
                _fetch(token_a, tenant_a) if i % 2 == 0 else _fetch(token_b, tenant_b)
                for i in range(20)
            ]
            results = await asyncio.gather(*requests)

    for index, response in enumerate(results):
        assert response.status_code == 200
        expected_role = "tenant_admin" if index % 2 == 0 else "developer"
        assert response.json()["role"] == expected_role
