"""Evaluation domain: datasets, versioned test cases, and immutable
dataset snapshots.

Revision ID: 0004_eval_domain_datasets
Revises: 0003_eval_domain_resources
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004_eval_domain_datasets"
down_revision: str | None = "0003_eval_domain_resources"
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
    op.execute("CREATE TYPE dataset_status AS ENUM ('active', 'archived')")
    op.execute("CREATE TYPE test_case_status AS ENUM ('active', 'archived')")
    op.execute("CREATE TYPE dataset_snapshot_status AS ENUM ('draft', 'finalized', 'archived')")

    op.execute(
        """
        CREATE TABLE datasets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            workspace_id UUID NOT NULL,
            name TEXT NOT NULL,
            status dataset_status NOT NULL DEFAULT 'active',
            created_by UUID NOT NULL REFERENCES users (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_datasets_id_tenant UNIQUE (id, tenant_id),
            CONSTRAINT fk_datasets_workspace
                FOREIGN KEY (workspace_id, tenant_id)
                REFERENCES workspaces (id, tenant_id) ON DELETE CASCADE
        )
        """
    )
    op.execute("CREATE INDEX ix_datasets_workspace_id ON datasets (workspace_id)")

    op.execute(
        """
        CREATE TABLE test_cases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            dataset_id UUID NOT NULL,
            external_key TEXT,
            status test_case_status NOT NULL DEFAULT 'active',
            created_by UUID NOT NULL REFERENCES users (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_test_cases_id_tenant UNIQUE (id, tenant_id),
            CONSTRAINT uq_test_cases_dataset_external_key UNIQUE (dataset_id, external_key),
            CONSTRAINT fk_test_cases_dataset
                FOREIGN KEY (dataset_id, tenant_id)
                REFERENCES datasets (id, tenant_id) ON DELETE CASCADE
        )
        """
    )
    op.execute("CREATE INDEX ix_test_cases_dataset_id ON test_cases (dataset_id)")

    op.execute(
        """
        CREATE TABLE test_case_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            test_case_id UUID NOT NULL,
            version_number INTEGER NOT NULL CHECK (version_number > 0),
            content JSONB NOT NULL,
            content_hash TEXT NOT NULL,
            hash_algorithm TEXT NOT NULL,
            canonicalization_version TEXT NOT NULL,
            retention_class retention_class NOT NULL DEFAULT 'standard',
            retain_until TIMESTAMPTZ,
            archived_at TIMESTAMPTZ,
            is_immutable_evidence BOOLEAN NOT NULL DEFAULT true,
            created_by UUID NOT NULL REFERENCES users (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_test_case_versions_id_tenant UNIQUE (id, tenant_id),
            CONSTRAINT uq_test_case_versions_case_version UNIQUE (test_case_id, version_number),
            CONSTRAINT fk_test_case_versions_test_case
                FOREIGN KEY (test_case_id, tenant_id)
                REFERENCES test_cases (id, tenant_id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_test_case_versions_test_case_id ON test_case_versions (test_case_id)"
    )

    op.execute(
        """
        CREATE TABLE dataset_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            dataset_id UUID NOT NULL,
            status dataset_snapshot_status NOT NULL DEFAULT 'draft',
            content_hash TEXT,
            hash_algorithm TEXT,
            canonicalization_version TEXT,
            item_count INTEGER NOT NULL DEFAULT 0,
            retention_class retention_class NOT NULL DEFAULT 'standard',
            retain_until TIMESTAMPTZ,
            archived_at TIMESTAMPTZ,
            created_by UUID NOT NULL REFERENCES users (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finalized_by UUID REFERENCES users (id),
            finalized_at TIMESTAMPTZ,
            CONSTRAINT uq_dataset_snapshots_id_tenant UNIQUE (id, tenant_id),
            CONSTRAINT fk_dataset_snapshots_dataset
                FOREIGN KEY (dataset_id, tenant_id)
                REFERENCES datasets (id, tenant_id) ON DELETE CASCADE
        )
        """
    )
    op.execute("CREATE INDEX ix_dataset_snapshots_dataset_id ON dataset_snapshots (dataset_id)")

    op.execute(
        """
        CREATE TABLE dataset_snapshot_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            snapshot_id UUID NOT NULL,
            test_case_version_id UUID NOT NULL,
            sequence_index INTEGER NOT NULL CHECK (sequence_index >= 0),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_dataset_snapshot_items_snapshot_sequence
                UNIQUE (snapshot_id, sequence_index),
            CONSTRAINT uq_dataset_snapshot_items_snapshot_version
                UNIQUE (snapshot_id, test_case_version_id),
            CONSTRAINT fk_dataset_snapshot_items_snapshot
                FOREIGN KEY (snapshot_id, tenant_id)
                REFERENCES dataset_snapshots (id, tenant_id) ON DELETE CASCADE,
            CONSTRAINT fk_dataset_snapshot_items_test_case_version
                FOREIGN KEY (test_case_version_id, tenant_id)
                REFERENCES test_case_versions (id, tenant_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_dataset_snapshot_items_snapshot_id ON dataset_snapshot_items (snapshot_id)"
    )

    # Immutability, enforced independently of grants: a finalized
    # snapshot's own row (hash, item_count, status) can never be
    # updated again, and membership rows can only be inserted while
    # the parent snapshot is still a draft and must belong to the
    # snapshot's own dataset — closing the gap application code alone
    # could leave open (see docs/adr/0002).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_finalized_snapshot_mutation() RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status = 'finalized' THEN
                RAISE EXCEPTION 'dataset snapshot % is immutable after finalization', OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_forbid_finalized_snapshot_mutation
        BEFORE UPDATE ON dataset_snapshots
        FOR EACH ROW EXECUTE FUNCTION forbid_finalized_snapshot_mutation()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_snapshot_item() RETURNS TRIGGER AS $$
        DECLARE
            snapshot_status dataset_snapshot_status;
            snapshot_dataset_id UUID;
            item_dataset_id UUID;
        BEGIN
            SELECT status, dataset_id INTO snapshot_status, snapshot_dataset_id
            FROM dataset_snapshots WHERE id = NEW.snapshot_id;
            IF snapshot_status IS DISTINCT FROM 'draft' THEN
                RAISE EXCEPTION
                    'dataset snapshot % is not a draft; membership cannot change', NEW.snapshot_id;
            END IF;
            SELECT tc.dataset_id INTO item_dataset_id
            FROM test_case_versions tcv JOIN test_cases tc ON tc.id = tcv.test_case_id
            WHERE tcv.id = NEW.test_case_version_id;
            IF item_dataset_id IS DISTINCT FROM snapshot_dataset_id THEN
                RAISE EXCEPTION
                    'test-case version % does not belong to snapshot %''s dataset',
                    NEW.test_case_version_id, NEW.snapshot_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validate_snapshot_item
        BEFORE INSERT ON dataset_snapshot_items
        FOR EACH ROW EXECUTE FUNCTION validate_snapshot_item()
        """
    )

    for table in ("datasets", "test_cases", "test_case_versions", "dataset_snapshots"):
        _enable_rls(table)
    _enable_rls("dataset_snapshot_items")

    op.execute(f"GRANT SELECT, INSERT ON datasets TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON test_cases TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON test_case_versions TO {_APP_ROLE}")
    # UPDATE is required only for the draft -> finalized transition;
    # the trigger above blocks every update once status is finalized.
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON dataset_snapshots TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON dataset_snapshot_items TO {_APP_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON dataset_snapshot_items FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON dataset_snapshots FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON test_case_versions FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON test_cases FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON datasets FROM {_APP_ROLE}")
    op.execute("DROP TRIGGER IF EXISTS trg_validate_snapshot_item ON dataset_snapshot_items")
    op.execute("DROP FUNCTION IF EXISTS validate_snapshot_item()")
    op.execute("DROP TRIGGER IF EXISTS trg_forbid_finalized_snapshot_mutation ON dataset_snapshots")
    op.execute("DROP FUNCTION IF EXISTS forbid_finalized_snapshot_mutation()")
    op.execute("DROP TABLE IF EXISTS dataset_snapshot_items")
    op.execute("DROP TABLE IF EXISTS dataset_snapshots")
    op.execute("DROP TABLE IF EXISTS test_case_versions")
    op.execute("DROP TABLE IF EXISTS test_cases")
    op.execute("DROP TABLE IF EXISTS datasets")
    op.execute("DROP TYPE IF EXISTS dataset_snapshot_status")
    op.execute("DROP TYPE IF EXISTS test_case_status")
    op.execute("DROP TYPE IF EXISTS dataset_status")
