"""Identity and tenancy: users, tenants, tenant_memberships, and RLS

Revision ID: 0002_identity_and_tenancy
Revises: 0001_foundation_baseline
Create Date: 2026-08-15
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from alembic import op

revision: str = "0002_identity_and_tenancy"
down_revision: str | None = "0001_foundation_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "evalforge_app"


def _create_or_update_app_role() -> None:
    """Create the least-privilege role the running application connects
    as, distinct from the migration/admin role that owns these tables.

    Table owners and superusers always bypass row-level security, so
    without a separate, non-superuser role the RLS policies below on
    ``tenant_memberships`` would never actually apply to the running
    API process. The password comes only from the environment — it is
    never hardcoded in this file — and this migration fails closed if
    it is missing.
    """
    password = os.environ.get("EVALFORGE_APP_DB_PASSWORD")
    if not password:
        raise RuntimeError(
            "EVALFORGE_APP_DB_PASSWORD must be set in the environment running "
            "this migration so the least-privilege application role can be "
            "created or updated."
        )
    escaped_password = password.replace("'", "''")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{_APP_ROLE}') THEN
                CREATE ROLE {_APP_ROLE} LOGIN PASSWORD '{escaped_password}';
            ELSE
                ALTER ROLE {_APP_ROLE} WITH LOGIN PASSWORD '{escaped_password}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    _create_or_update_app_role()

    op.execute("CREATE TYPE user_kind AS ENUM ('human', 'service')")
    op.execute("CREATE TYPE user_status AS ENUM ('invited', 'active', 'disabled', 'removed')")
    op.execute(
        "CREATE TYPE tenant_status AS ENUM ('provisioned', 'active', 'suspended', 'deleted')"
    )
    op.execute(
        "CREATE TYPE tenant_role AS ENUM "
        "('tenant_admin', 'evaluation_engineer', 'developer', 'reviewer', 'read_only_observer')"
    )
    op.execute(
        "CREATE TYPE membership_status AS ENUM ('invited', 'active', 'suspended', 'removed')"
    )

    op.execute(
        """
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            kind user_kind NOT NULL DEFAULT 'human',
            status user_status NOT NULL DEFAULT 'active',
            auth_provider TEXT NOT NULL DEFAULT 'local',
            provider_subject TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_users_email UNIQUE (email),
            CONSTRAINT uq_users_provider_subject UNIQUE (auth_provider, provider_subject)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE tenants (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug TEXT NOT NULL,
            name TEXT NOT NULL,
            status tenant_status NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_tenants_slug UNIQUE (slug)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE tenant_memberships (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
            role tenant_role NOT NULL,
            status membership_status NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_tenant_memberships_user_tenant UNIQUE (user_id, tenant_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_tenant_memberships_tenant_id ON tenant_memberships (tenant_id)")
    op.execute("CREATE INDEX ix_tenant_memberships_user_id ON tenant_memberships (user_id)")

    # Defense-in-depth: row-level security restricts every read and
    # write on this tenant-owned table to rows the current transaction's
    # server-verified identity may see, even if application code omits a
    # tenant_id or user_id filter. FORCE is required because the
    # migration role owns the table, and table owners bypass RLS by
    # default. See evalforge_api.adapters.membership_repository for how
    # the session settings referenced below are populated per request.
    op.execute("ALTER TABLE tenant_memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_memberships FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_memberships_select ON tenant_memberships
        FOR SELECT
        USING (
            user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
            OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_memberships_insert ON tenant_memberships
        FOR INSERT
        WITH CHECK (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
        """
    )

    # Least privilege: the running application may only touch the rows
    # and columns its own request-serving code actually needs. It has
    # no DDL rights and, on tenant_memberships, is fully subject to the
    # RLS policies above rather than bypassing them as an owner would.
    op.execute(f"GRANT USAGE ON SCHEMA public TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON users TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT ON tenants TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON tenant_memberships TO {_APP_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON tenant_memberships FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON tenants FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON users FROM {_APP_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {_APP_ROLE}")
    op.execute("DROP TABLE IF EXISTS tenant_memberships")
    op.execute("DROP TABLE IF EXISTS tenants")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TYPE IF EXISTS membership_status")
    op.execute("DROP TYPE IF EXISTS tenant_role")
    op.execute("DROP TYPE IF EXISTS tenant_status")
    op.execute("DROP TYPE IF EXISTS user_status")
    op.execute("DROP TYPE IF EXISTS user_kind")
    op.execute(f"DROP ROLE IF EXISTS {_APP_ROLE}")
