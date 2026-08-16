"""Ingestion domain: runs and run tool-definition-version lineage.

Runs represent externally produced execution evidence submitted
through Milestone 5 ingestion; this migration does not implement
experiment scheduling or execution (Milestone 7).

Revision ID: 0006_ingestion_runs
Revises: 0005_eval_domain_artifacts
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_ingestion_runs"
down_revision: str | None = "0005_eval_domain_artifacts"
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
    op.execute("CREATE TYPE run_status AS ENUM ('running', 'completed', 'failed', 'canceled')")

    # Every optional lineage reference is a composite (id, tenant_id)
    # foreign key against the Milestone 4 tables it points to, so a
    # cross-tenant reference is impossible to insert regardless of
    # application-layer validation bugs (docs/TENANCY_AND_AUTHORIZATION.md).
    op.execute(
        """
        CREATE TABLE runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            workspace_id UUID NOT NULL,
            evaluation_target_id UUID,
            model_version_id UUID,
            prompt_version_id UUID,
            retrieval_config_version_id UUID,
            workflow_version_id UUID,
            pricing_version_id UUID,
            status run_status NOT NULL DEFAULT 'running',
            source TEXT NOT NULL,
            correlation_id TEXT,
            started_at TIMESTAMPTZ NOT NULL,
            ended_at TIMESTAMPTZ,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            schema_version TEXT NOT NULL,
            created_by UUID NOT NULL REFERENCES users (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finalized_at TIMESTAMPTZ,
            CONSTRAINT uq_runs_id_tenant UNIQUE (id, tenant_id),
            CONSTRAINT fk_runs_workspace
                FOREIGN KEY (workspace_id, tenant_id)
                REFERENCES workspaces (id, tenant_id) ON DELETE CASCADE,
            CONSTRAINT fk_runs_evaluation_target
                FOREIGN KEY (evaluation_target_id, tenant_id)
                REFERENCES evaluation_targets (id, tenant_id),
            CONSTRAINT fk_runs_model_version
                FOREIGN KEY (model_version_id, tenant_id)
                REFERENCES versioned_resource_versions (id, tenant_id),
            CONSTRAINT fk_runs_prompt_version
                FOREIGN KEY (prompt_version_id, tenant_id)
                REFERENCES versioned_resource_versions (id, tenant_id),
            CONSTRAINT fk_runs_retrieval_config_version
                FOREIGN KEY (retrieval_config_version_id, tenant_id)
                REFERENCES versioned_resource_versions (id, tenant_id),
            CONSTRAINT fk_runs_workflow_version
                FOREIGN KEY (workflow_version_id, tenant_id)
                REFERENCES versioned_resource_versions (id, tenant_id),
            CONSTRAINT fk_runs_pricing_version
                FOREIGN KEY (pricing_version_id, tenant_id)
                REFERENCES versioned_resource_versions (id, tenant_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_runs_workspace_id ON runs (workspace_id)")
    op.execute("CREATE INDEX ix_runs_tenant_status ON runs (tenant_id, status)")

    op.execute(
        """
        CREATE TABLE run_tool_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            run_id UUID NOT NULL,
            tool_definition_version_id UUID NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_run_tool_versions_run_tool UNIQUE (run_id, tool_definition_version_id),
            CONSTRAINT fk_run_tool_versions_run
                FOREIGN KEY (run_id, tenant_id)
                REFERENCES runs (id, tenant_id) ON DELETE CASCADE,
            CONSTRAINT fk_run_tool_versions_tool_version
                FOREIGN KEY (tool_definition_version_id, tenant_id)
                REFERENCES versioned_resource_versions (id, tenant_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_run_tool_versions_run_id ON run_tool_versions (run_id)")

    # Immutability: once a run reaches a terminal status, its own row
    # (and, via the trigger below, its tool-version lineage) can never
    # be updated again — matching forbid_finalized_snapshot_mutation
    # from the evaluation-domain migration exactly. Reruns or
    # materially different evidence must create a new run
    # (docs/REPRODUCIBILITY_CONTRACT.md).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_terminal_run_mutation() RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status IN ('completed', 'failed', 'canceled') THEN
                RAISE EXCEPTION 'run % is immutable once terminal (status=%)', OLD.id, OLD.status;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_forbid_terminal_run_mutation
        BEFORE UPDATE ON runs
        FOR EACH ROW EXECUTE FUNCTION forbid_terminal_run_mutation()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_run_tool_version_insert() RETURNS TRIGGER AS $$
        DECLARE
            run_status_value run_status;
        BEGIN
            SELECT status INTO run_status_value FROM runs WHERE id = NEW.run_id;
            IF run_status_value IN ('completed', 'failed', 'canceled') THEN
                RAISE EXCEPTION
                    'run % is terminal; tool-version lineage can no longer change', NEW.run_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validate_run_tool_version_insert
        BEFORE INSERT ON run_tool_versions
        FOR EACH ROW EXECUTE FUNCTION validate_run_tool_version_insert()
        """
    )

    _enable_rls("runs")
    _enable_rls("run_tool_versions")

    # UPDATE is required only for the running -> terminal transition;
    # the trigger above blocks every update once a run is terminal.
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON runs TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON run_tool_versions TO {_APP_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON run_tool_versions FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON runs FROM {_APP_ROLE}")
    op.execute("DROP TRIGGER IF EXISTS trg_validate_run_tool_version_insert ON run_tool_versions")
    op.execute("DROP FUNCTION IF EXISTS validate_run_tool_version_insert()")
    op.execute("DROP TRIGGER IF EXISTS trg_forbid_terminal_run_mutation ON runs")
    op.execute("DROP FUNCTION IF EXISTS forbid_terminal_run_mutation()")
    op.execute("DROP TABLE IF EXISTS run_tool_versions")
    op.execute("DROP TABLE IF EXISTS runs")
    op.execute("DROP TYPE IF EXISTS run_status")
