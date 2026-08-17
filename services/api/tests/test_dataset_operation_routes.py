"""HTTP surface for the bulk dataset operations: import, export,
duplicate check, clone, sampling, splitting — and the cross-tenant
responses each of them must give.
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


async def test_import_export_clone_sample_and_split_over_http(
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
        slug="tenant-io",
        email="engineer-io@example.com",
    )
    token = _login(api_client, "engineer-io@example.com")
    dataset_id = api_client.post(
        f"/tenants/{tenant_id}/datasets",
        json={"workspace_id": str(workspace_id), "name": "IO"},
        headers=_auth(token),
    ).json()["id"]

    document = "\n".join(f'{{"input": "question {index}"}}' for index in range(6)) + "\n"
    imported = api_client.post(
        f"/tenants/{tenant_id}/datasets/{dataset_id}/import",
        files={"file": ("cases.jsonl", document, "application/x-ndjson")},
        data={"format": "jsonl"},
        headers=_auth(token),
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["committed"] is True
    assert imported.json()["record_count"] == 6
    assert imported.json()["failed_record_count"] == 0

    rejected = api_client.post(
        f"/tenants/{tenant_id}/datasets/{dataset_id}/import",
        files={"file": ("bad.jsonl", '{"input": "ok"}\n{"no_input": true}\n', "application/json")},
        data={"format": "jsonl"},
        headers=_auth(token),
    )
    assert rejected.status_code == 200
    assert rejected.json()["committed"] is False
    assert rejected.json()["failed_record_count"] == 1
    assert rejected.json()["records"][1]["row_index"] == 2

    exported = api_client.get(
        f"/tenants/{tenant_id}/datasets/{dataset_id}/export",
        params={"format": "jsonl"},
        headers=_auth(token),
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/x-ndjson")
    assert dataset_id in exported.text
    assert len(exported.text.strip().split("\n")) == 7  # header + 6 records

    duplicate = api_client.post(
        f"/tenants/{tenant_id}/datasets/{dataset_id}/duplicate-check",
        json={"content": {"input": "  QUESTION 0 "}},
        headers=_auth(token),
    )
    assert duplicate.status_code == 200
    assert len(duplicate.json()["duplicate_test_case_ids"]) == 1

    clone = api_client.post(
        f"/tenants/{tenant_id}/datasets/{dataset_id}/clone",
        json={"new_name": "IO clone"},
        headers=_auth(token),
    )
    assert clone.status_code == 201, clone.text
    assert clone.json()["source"] == "cloned"
    assert clone.json()["cloned_from_dataset_id"] == dataset_id

    snapshot_id = api_client.post(
        f"/tenants/{tenant_id}/datasets/{dataset_id}/snapshots", headers=_auth(token)
    ).json()["id"]
    version_ids = [
        item["versions"][0]["id"]
        for item in [
            api_client.get(
                f"/tenants/{tenant_id}/test-cases/{case['id']}/versions", headers=_auth(token)
            ).json()
            for case in api_client.get(
                f"/tenants/{tenant_id}/datasets/{dataset_id}/test-cases", headers=_auth(token)
            ).json()["test_cases"]
        ]
    ]
    for index, version_id in enumerate(version_ids):
        api_client.post(
            f"/tenants/{tenant_id}/snapshots/{snapshot_id}/items",
            json={"test_case_version_id": version_id, "sequence_index": index},
            headers=_auth(token),
        )

    # Sampling a draft is refused; finalizing first makes it stable.
    draft_sample = api_client.post(
        f"/tenants/{tenant_id}/snapshots/{snapshot_id}/sample",
        json={"sample_size": 2, "seed": "abc"},
        headers=_auth(token),
    )
    assert draft_sample.status_code == 422

    api_client.post(f"/tenants/{tenant_id}/snapshots/{snapshot_id}/finalize", headers=_auth(token))
    sampled = api_client.post(
        f"/tenants/{tenant_id}/snapshots/{snapshot_id}/sample",
        json={"sample_size": 2, "seed": "abc"},
        headers=_auth(token),
    )
    assert sampled.status_code == 200
    assert len(sampled.json()["test_case_version_ids"]) == 2

    split = api_client.post(
        f"/tenants/{tenant_id}/snapshots/{snapshot_id}/split",
        json={"ratios": {"train": 0.5, "test": 0.5}, "seed": "abc"},
        headers=_auth(token),
    )
    assert split.status_code == 200
    buckets = split.json()["buckets"]
    assert sorted(buckets["train"] + buckets["test"]) == sorted(version_ids)


async def test_cross_tenant_dataset_access_over_http_is_not_found(
    api_client: TestClient,
    identity_repositories: IdentityRepositories,
    evaluation_repositories: EvaluationRepositories,
    build_tenant_context: BuildContext,
    create_tenant: CreateTenant,
) -> None:
    tenant_a, workspace_a = await _setup_tenant(
        identity_repositories=identity_repositories,
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        slug="tenant-x",
        email="engineer-x@example.com",
    )
    tenant_b, workspace_b = await _setup_tenant(
        identity_repositories=identity_repositories,
        evaluation_repositories=evaluation_repositories,
        build_tenant_context=build_tenant_context,
        create_tenant=create_tenant,
        slug="tenant-y",
        email="engineer-y@example.com",
    )
    token_a = _login(api_client, "engineer-x@example.com")
    token_b = _login(api_client, "engineer-y@example.com")

    dataset_b = api_client.post(
        f"/tenants/{tenant_b}/datasets",
        json={"workspace_id": str(workspace_b), "name": "B private"},
        headers=_auth(token_b),
    ).json()["id"]

    # Tenant A asking within its own tenant path: not found.
    assert (
        api_client.get(
            f"/tenants/{tenant_a}/datasets/{dataset_b}", headers=_auth(token_a)
        ).status_code
        == 404
    )
    assert (
        api_client.patch(
            f"/tenants/{tenant_a}/datasets/{dataset_b}",
            json={"name": "Hijacked"},
            headers=_auth(token_a),
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            f"/tenants/{tenant_a}/datasets/{dataset_b}/clone",
            json={"new_name": "Stolen"},
            headers=_auth(token_a),
        ).status_code
        == 404
    )
    # Tenant A pointing at Tenant B's tenant path: forbidden, not found.
    assert (
        api_client.get(
            f"/tenants/{tenant_b}/datasets/{dataset_b}", headers=_auth(token_a)
        ).status_code
        == 403
    )
    del workspace_a
