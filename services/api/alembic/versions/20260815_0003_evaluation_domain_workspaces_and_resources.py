"""Evaluation domain: workspaces, evaluation targets, and versioned
configuration resources (model/prompt/retrieval/tool/workflow/
evaluator/pricing versions).

Revision ID: 0003_eval_domain_resources
Revises: 0002_identity_and_tenancy
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_eval_domain_resources"
down_revision: str | None = "0002_identity_and_tenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "evalforge_app"

# Defense-in-depth, matching the identity-and-tenancy migration: every
# tenant-owned table gets RLS keyed on the transaction-local
# app.current_tenant_id setting the repository layer populates from
# server-verified identity, plus the same FORCE requirement so the
# migration/admin role (the table owner) cannot bypass it either.
_TENANT_ISOLATION_POLICY = """
CREATE POLICY {table}_tenant_isolation ON {table}
FOR ALL
USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
"""


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(_TENANT_ISOLATION_POLICY.format(table=table))


def upgrade() -> None:
    op.execute(
        "CREATE TYPE resource_kind AS ENUM ("
        "'model_config', 'prompt_config', 'retrieval_config', 'tool_definition', "
        "'workflow_definition', 'evaluator_definition', 'pricing_assumption')"
    )
    op.execute(
        "CREATE TYPE versioned_resource_status AS ENUM "
        "('drafted', 'active', 'deprecated', 'archived')"
    )
    op.execute("CREATE TYPE workspace_status AS ENUM ('active', 'archived')")
    op.execute(
        "CREATE TYPE evaluation_target_status AS ENUM "
        "('registered', 'active', 'deprecated', 'archived')"
    )
    # Shared by this and later evaluation-domain migrations.
    op.execute("CREATE TYPE retention_class AS ENUM ('standard', 'extended', 'legal_hold')")

    op.execute(
        """
        CREATE TABLE workspaces (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
            slug TEXT NOT NULL,
            name TEXT NOT NULL,
            status workspace_status NOT NULL DEFAULT 'active',
            created_by UUID NOT NULL REFERENCES users (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_workspaces_id_tenant UNIQUE (id, tenant_id),
            CONSTRAINT uq_workspaces_tenant_slug UNIQUE (tenant_id, slug)
        )
        """
    )
    op.execute("CREATE INDEX ix_workspaces_tenant_id ON workspaces (tenant_id)")

    op.execute(
        """
        CREATE TABLE evaluation_targets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            workspace_id UUID NOT NULL,
            name TEXT NOT NULL,
            target_type TEXT NOT NULL,
            status evaluation_target_status NOT NULL DEFAULT 'registered',
            created_by UUID NOT NULL REFERENCES users (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_evaluation_targets_id_tenant UNIQUE (id, tenant_id),
            CONSTRAINT fk_evaluation_targets_workspace
                FOREIGN KEY (workspace_id, tenant_id)
                REFERENCES workspaces (id, tenant_id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_evaluation_targets_workspace_id ON evaluation_targets (workspace_id)"
    )
    op.execute("CREATE INDEX ix_evaluation_targets_tenant_id ON evaluation_targets (tenant_id)")

    op.execute(
        """
        CREATE TABLE versioned_resources (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            workspace_id UUID NOT NULL,
            kind resource_kind NOT NULL,
            name TEXT NOT NULL,
            status versioned_resource_status NOT NULL DEFAULT 'drafted',
            created_by UUID NOT NULL REFERENCES users (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_versioned_resources_id_tenant UNIQUE (id, tenant_id),
            CONSTRAINT fk_versioned_resources_workspace
                FOREIGN KEY (workspace_id, tenant_id)
                REFERENCES workspaces (id, tenant_id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_versioned_resources_workspace_id ON versioned_resources (workspace_id)"
    )
    op.execute(
        "CREATE INDEX ix_versioned_resources_tenant_kind ON versioned_resources (tenant_id, kind)"
    )

    # Composite (id, tenant_id) foreign keys throughout this and later
    # evaluation-domain migrations are the primary tenant-isolation
    # integrity layer: a child row's tenant_id must match its parent
    # row's tenant_id at the database level, so no application bug or
    # crafted request can attach one tenant's child to another
    # tenant's parent — the constraint makes the cross-tenant
    # reference impossible to insert, independent of RLS.
    op.execute(
        """
        CREATE TABLE versioned_resource_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            resource_id UUID NOT NULL,
            version_number INTEGER NOT NULL CHECK (version_number > 0),
            content JSONB NOT NULL,
            content_hash TEXT NOT NULL,
            hash_algorithm TEXT NOT NULL,
            canonicalization_version TEXT NOT NULL,
            derived_from_version_id UUID,
            retention_class retention_class NOT NULL DEFAULT 'standard',
            retain_until TIMESTAMPTZ,
            archived_at TIMESTAMPTZ,
            is_immutable_evidence BOOLEAN NOT NULL DEFAULT true,
            created_by UUID NOT NULL REFERENCES users (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_versioned_resource_versions_id_tenant UNIQUE (id, tenant_id),
            CONSTRAINT uq_versioned_resource_versions_resource_version
                UNIQUE (resource_id, version_number),
            CONSTRAINT fk_versioned_resource_versions_resource
                FOREIGN KEY (resource_id, tenant_id)
                REFERENCES versioned_resources (id, tenant_id) ON DELETE CASCADE,
            CONSTRAINT fk_versioned_resource_versions_derived_from
                FOREIGN KEY (derived_from_version_id, tenant_id)
                REFERENCES versioned_resource_versions (id, tenant_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_versioned_resource_versions_resource_id "
        "ON versioned_resource_versions (resource_id)"
    )

    # The composite (id, tenant_id) foreign key above only guarantees
    # a derived-from version belongs to the same tenant. This trigger
    # closes the remaining gap so a version can never claim lineage
    # from a different logical resource, matching
    # evalforge_api.domain.versioning.validate_lineage_within_resource.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_resource_version_lineage() RETURNS TRIGGER AS $$
        DECLARE
            parent_resource_id UUID;
        BEGIN
            IF NEW.derived_from_version_id IS NULL THEN
                RETURN NEW;
            END IF;
            SELECT resource_id INTO parent_resource_id
            FROM versioned_resource_versions WHERE id = NEW.derived_from_version_id;
            IF parent_resource_id IS DISTINCT FROM NEW.resource_id THEN
                RAISE EXCEPTION
                    'version % may only derive from a version of its own resource', NEW.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validate_resource_version_lineage
        BEFORE INSERT ON versioned_resource_versions
        FOR EACH ROW EXECUTE FUNCTION validate_resource_version_lineage()
        """
    )

    for table in (
        "workspaces",
        "evaluation_targets",
        "versioned_resources",
        "versioned_resource_versions",
    ):
        _enable_rls(table)

    # Least privilege: no UPDATE or DELETE grant anywhere in this
    # migration. Versions are immutable by construction — the only
    # supported write is INSERT of a new row — and workspace/target/
    # resource metadata mutation is out of Milestone 4 scope.
    op.execute(f"GRANT SELECT, INSERT ON workspaces TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON evaluation_targets TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON versioned_resources TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON versioned_resource_versions TO {_APP_ROLE}")


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_validate_resource_version_lineage "
        "ON versioned_resource_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS validate_resource_version_lineage()")
    op.execute(f"REVOKE ALL ON versioned_resource_versions FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON versioned_resources FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON evaluation_targets FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON workspaces FROM {_APP_ROLE}")
    op.execute("DROP TABLE IF EXISTS versioned_resource_versions")
    op.execute("DROP TABLE IF EXISTS versioned_resources")
    op.execute("DROP TABLE IF EXISTS evaluation_targets")
    op.execute("DROP TABLE IF EXISTS workspaces")
    op.execute("DROP TYPE IF EXISTS retention_class")
    op.execute("DROP TYPE IF EXISTS evaluation_target_status")
    op.execute("DROP TYPE IF EXISTS workspace_status")
    op.execute("DROP TYPE IF EXISTS versioned_resource_status")
    op.execute("DROP TYPE IF EXISTS resource_kind")
