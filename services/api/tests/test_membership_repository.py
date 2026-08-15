from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import asyncpg
import pytest

from evalforge_api.adapters.user_repository import EmailAlreadyRegisteredError
from evalforge_api.domain.enums import TenantRole, UserKind
from evalforge_api.ports.identity import IdentityRepositories
from evalforge_api.settings import Settings

CreateTenant = Callable[..., Awaitable[UUID]]


async def test_migration_head_revision_is_applied(test_settings: Settings) -> None:
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        row = await connection.fetchrow("SELECT version_num FROM alembic_version")
    finally:
        await connection.close()
    assert row is not None
    assert row["version_num"] == "0002_identity_and_tenancy"


async def test_creating_membership_for_unknown_user_fails_with_foreign_key_violation(
    identity_repositories: IdentityRepositories, create_tenant: CreateTenant
) -> None:
    tenant_id = await create_tenant("acme")

    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await identity_repositories.memberships.create(
            user_id=uuid4(), tenant_id=tenant_id, role=TenantRole.DEVELOPER
        )


async def test_creating_duplicate_membership_fails_with_unique_violation(
    identity_repositories: IdentityRepositories, create_tenant: CreateTenant
) -> None:
    tenant_id = await create_tenant("acme")
    user = await identity_repositories.users.create(
        email="dup@example.com", password_hash="irrelevant-hash-value", kind=UserKind.HUMAN
    )
    await identity_repositories.memberships.create(
        user_id=user.id, tenant_id=tenant_id, role=TenantRole.DEVELOPER
    )

    with pytest.raises(asyncpg.UniqueViolationError):
        await identity_repositories.memberships.create(
            user_id=user.id, tenant_id=tenant_id, role=TenantRole.TENANT_ADMIN
        )


async def test_tenant_slug_uniqueness_enforced(create_tenant: CreateTenant) -> None:
    await create_tenant("acme")
    with pytest.raises(asyncpg.UniqueViolationError):
        await create_tenant("acme")


async def test_user_email_uniqueness_enforced(identity_repositories: IdentityRepositories) -> None:
    await identity_repositories.users.create(
        email="dup2@example.com", password_hash="irrelevant-hash-value", kind=UserKind.HUMAN
    )
    with pytest.raises(EmailAlreadyRegisteredError):
        await identity_repositories.users.create(
            email="DUP2@example.com", password_hash="another-hash-value", kind=UserKind.HUMAN
        )


async def test_list_for_tenant_never_returns_another_tenants_rows(
    identity_repositories: IdentityRepositories, create_tenant: CreateTenant
) -> None:
    tenant_a = await create_tenant("tenant-a")
    tenant_b = await create_tenant("tenant-b")
    user_a = await identity_repositories.users.create(
        email="a@example.com", password_hash="hash-a", kind=UserKind.HUMAN
    )
    user_b = await identity_repositories.users.create(
        email="b@example.com", password_hash="hash-b", kind=UserKind.HUMAN
    )
    await identity_repositories.memberships.create(
        user_id=user_a.id, tenant_id=tenant_a, role=TenantRole.TENANT_ADMIN
    )
    await identity_repositories.memberships.create(
        user_id=user_b.id, tenant_id=tenant_b, role=TenantRole.TENANT_ADMIN
    )

    members_of_a = await identity_repositories.memberships.list_for_tenant(
        tenant_id=tenant_a, requesting_user_id=user_a.id
    )

    assert {member.user_id for member in members_of_a} == {user_a.id}


async def test_row_level_security_denies_reads_with_no_session_context(
    identity_repositories: IdentityRepositories,
    create_tenant: CreateTenant,
    test_settings: Settings,
) -> None:
    tenant_id = await create_tenant("acme")
    user = await identity_repositories.users.create(
        email="owner@example.com", password_hash="irrelevant-hash-value", kind=UserKind.HUMAN
    )
    await identity_repositories.memberships.create(
        user_id=user.id, tenant_id=tenant_id, role=TenantRole.TENANT_ADMIN
    )

    # Connect as the least-privilege application role with no session
    # settings established. The row exists, but RLS denies the read.
    connection = await asyncpg.connect(dsn=str(test_settings.app_database_url))
    try:
        rows = await connection.fetch("SELECT * FROM tenant_memberships")
    finally:
        await connection.close()

    assert rows == []
