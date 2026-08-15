"""Local-development seed data for exercising Milestone 3 end-to-end.

Refuses to run against a production environment. Not exposed through
any HTTP endpoint: self-service tenant and account creation is out of
scope for Milestone 3, so this script is the only supported way to
create the tenants and memberships needed to exercise the API locally.

Usage: python -m evalforge_api.dev_seed
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from uuid import UUID

import asyncpg
import structlog

from evalforge_api.adapters.membership_repository import PostgresMembershipRepository
from evalforge_api.adapters.postgres_pool import create_pool
from evalforge_api.adapters.user_repository import PostgresUserRepository
from evalforge_api.domain.enums import TenantRole, UserKind
from evalforge_api.security.passwords import hash_password
from evalforge_api.settings import get_settings

logger = structlog.get_logger(__name__)

# Synthetic local-dev-only value; seed() refuses to run in production.
SEED_PASSPHRASE = "Seed-Passphrase-2026!"  # noqa: S105


@dataclass(frozen=True, slots=True)
class SeedTenant:
    slug: str
    name: str


@dataclass(frozen=True, slots=True)
class SeedMember:
    email: str
    tenant_slug: str
    role: TenantRole


SEED_TENANTS = (
    SeedTenant(slug="acme", name="Acme Evaluation Team"),
    SeedTenant(slug="globex", name="Globex Evaluation Team"),
)

SEED_MEMBERS = (
    SeedMember(email="admin@acme.example", tenant_slug="acme", role=TenantRole.TENANT_ADMIN),
    SeedMember(email="member@acme.example", tenant_slug="acme", role=TenantRole.DEVELOPER),
    SeedMember(email="admin@globex.example", tenant_slug="globex", role=TenantRole.TENANT_ADMIN),
)


async def _ensure_tenant(pool: asyncpg.Pool, tenant: SeedTenant) -> UUID:
    async with pool.acquire() as connection:
        row = await connection.fetchrow(
            """
            INSERT INTO tenants (slug, name)
            VALUES ($1, $2)
            ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            tenant.slug,
            tenant.name,
        )
    assert row is not None
    return UUID(str(row["id"]))


async def _ensure_user(users: PostgresUserRepository, email: str) -> UUID:
    existing = await users.get_by_email(email)
    if existing is not None:
        return existing.id
    created = await users.create(
        email=email, password_hash=hash_password(SEED_PASSPHRASE), kind=UserKind.HUMAN
    )
    return created.id


async def seed() -> None:
    settings = get_settings()
    if settings.is_production:
        print("Refusing to seed development data into a production environment.", file=sys.stderr)
        raise SystemExit(1)

    # Uses the administrative DSN, not app_database_url: seeding tenants
    # is a trusted local-operator action, and the least-privilege
    # runtime role intentionally cannot create tenants (see the M3
    # migration's grants).
    pool = await create_pool(str(settings.database_url))
    try:
        users = PostgresUserRepository(pool)
        memberships = PostgresMembershipRepository(pool)

        tenant_ids = {tenant.slug: await _ensure_tenant(pool, tenant) for tenant in SEED_TENANTS}

        for member in SEED_MEMBERS:
            user_id = await _ensure_user(users, member.email)
            tenant_id = tenant_ids[member.tenant_slug]
            existing_membership = await memberships.get_membership(
                user_id=user_id, tenant_id=tenant_id
            )
            if existing_membership is None:
                await memberships.create(user_id=user_id, tenant_id=tenant_id, role=member.role)

        print("Seed complete. Local-only accounts (never valid outside this stack):")
        for member in SEED_MEMBERS:
            print(
                f"  {member.email} / {SEED_PASSPHRASE}"
                f" -> {member.tenant_slug} ({member.role.value})"
            )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(seed())
