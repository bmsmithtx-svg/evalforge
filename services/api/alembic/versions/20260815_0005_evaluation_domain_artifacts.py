"""Evaluation domain: artifact metadata and immutable artifact versions.

Object bytes live in S3-compatible object storage
(``evalforge_api.adapters.artifact_object_storage``); this migration
only creates the PostgreSQL metadata, hash, and lineage records that
reference them by tenant-scoped storage key.

Revision ID: 0005_eval_domain_artifacts
Revises: 0004_eval_domain_datasets
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005_eval_domain_artifacts"
down_revision: str | None = "0004_eval_domain_datasets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "evalforge_app"

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
        "CREATE TYPE artifact_status AS ENUM ('uploaded', 'validated', 'referenced', 'archived')"
    )

    op.execute(
        """
        CREATE TABLE artifacts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
            workspace_id UUID,
            media_type TEXT NOT NULL,
            purpose TEXT NOT NULL,
            status artifact_status NOT NULL DEFAULT 'uploaded',
            created_by UUID NOT NULL REFERENCES users (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_artifacts_id_tenant UNIQUE (id, tenant_id),
            CONSTRAINT fk_artifacts_workspace
                FOREIGN KEY (workspace_id, tenant_id)
                REFERENCES workspaces (id, tenant_id) ON DELETE CASCADE
        )
        """
    )
    op.execute("CREATE INDEX ix_artifacts_tenant_id ON artifacts (tenant_id)")

    # Composite (id, tenant_id) foreign keys again make cross-tenant
    # lineage (an artifact version claiming to derive from another
    # tenant's version) impossible to insert at the database level.
    op.execute(
        """
        CREATE TABLE artifact_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            artifact_id UUID NOT NULL,
            version_number INTEGER NOT NULL CHECK (version_number > 0),
            content_hash TEXT NOT NULL,
            hash_algorithm TEXT NOT NULL,
            byte_size BIGINT NOT NULL CHECK (byte_size >= 0),
            content_type TEXT NOT NULL,
            storage_key TEXT NOT NULL,
            derived_from_artifact_version_id UUID,
            retention_class retention_class NOT NULL DEFAULT 'standard',
            retain_until TIMESTAMPTZ,
            archived_at TIMESTAMPTZ,
            is_immutable_evidence BOOLEAN NOT NULL DEFAULT true,
            created_by UUID NOT NULL REFERENCES users (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_artifact_versions_id_tenant UNIQUE (id, tenant_id),
            CONSTRAINT uq_artifact_versions_artifact_version UNIQUE (artifact_id, version_number),
            CONSTRAINT uq_artifact_versions_storage_key UNIQUE (storage_key),
            CONSTRAINT fk_artifact_versions_artifact
                FOREIGN KEY (artifact_id, tenant_id)
                REFERENCES artifacts (id, tenant_id) ON DELETE CASCADE,
            CONSTRAINT fk_artifact_versions_derived_from
                FOREIGN KEY (derived_from_artifact_version_id, tenant_id)
                REFERENCES artifact_versions (id, tenant_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_artifact_versions_artifact_id ON artifact_versions (artifact_id)")

    # Same defense-in-depth as versioned_resource_versions: the
    # composite (id, tenant_id) foreign key above only guarantees a
    # derived-from version belongs to the same tenant, not the same
    # logical artifact.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_artifact_version_lineage() RETURNS TRIGGER AS $$
        DECLARE
            parent_artifact_id UUID;
        BEGIN
            IF NEW.derived_from_artifact_version_id IS NULL THEN
                RETURN NEW;
            END IF;
            SELECT artifact_id INTO parent_artifact_id
            FROM artifact_versions WHERE id = NEW.derived_from_artifact_version_id;
            IF parent_artifact_id IS DISTINCT FROM NEW.artifact_id THEN
                RAISE EXCEPTION
                    'artifact version % may only derive from a version of its own artifact', NEW.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validate_artifact_version_lineage
        BEFORE INSERT ON artifact_versions
        FOR EACH ROW EXECUTE FUNCTION validate_artifact_version_lineage()
        """
    )

    _enable_rls("artifacts")
    _enable_rls("artifact_versions")

    # Least privilege: no UPDATE or DELETE. Artifact-version rows are
    # immutable evidence from the moment their bytes are verified and
    # persisted; artifact metadata rows are created once per logical
    # artifact and never mutated in this milestone.
    op.execute(f"GRANT SELECT, INSERT ON artifacts TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON artifact_versions TO {_APP_ROLE}")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_validate_artifact_version_lineage ON artifact_versions")
    op.execute("DROP FUNCTION IF EXISTS validate_artifact_version_lineage()")
    op.execute(f"REVOKE ALL ON artifact_versions FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON artifacts FROM {_APP_ROLE}")
    op.execute("DROP TABLE IF EXISTS artifact_versions")
    op.execute("DROP TABLE IF EXISTS artifacts")
    op.execute("DROP TYPE IF EXISTS artifact_status")
