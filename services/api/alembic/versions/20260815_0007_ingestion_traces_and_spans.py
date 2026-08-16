"""Ingestion domain: canonical traces and spans.

A trace is appendable while ``ingesting`` and immutable once
``finalized``; a span may only be inserted while its parent trace is
still ``ingesting``. See docs/DOMAIN_MODEL.md and the OpenTelemetry-
interoperability boundary in docs/ARCHITECTURE.md — ``provider_*_id``
columns carry the caller's external identifiers, never used as the
primary key, so EvalForge's canonical identity never depends on a
vendor's ID scheme.

Revision ID: 0007_ingestion_traces_spans
Revises: 0006_ingestion_runs
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007_ingestion_traces_spans"
down_revision: str | None = "0006_ingestion_runs"
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
    op.execute("CREATE TYPE trace_status AS ENUM ('ingesting', 'finalized')")
    op.execute(
        "CREATE TYPE span_kind AS ENUM "
        "('llm_call', 'retrieval_call', 'tool_call', 'workflow_step', 'other')"
    )
    op.execute("CREATE TYPE span_status AS ENUM ('ok', 'error')")

    op.execute(
        """
        CREATE TABLE traces (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            workspace_id UUID NOT NULL,
            run_id UUID NOT NULL,
            status trace_status NOT NULL DEFAULT 'ingesting',
            source TEXT NOT NULL,
            provider_trace_id TEXT,
            correlation_id TEXT,
            started_at TIMESTAMPTZ,
            ended_at TIMESTAMPTZ,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            schema_version TEXT NOT NULL,
            created_by UUID NOT NULL REFERENCES users (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finalized_at TIMESTAMPTZ,
            CONSTRAINT uq_traces_id_tenant UNIQUE (id, tenant_id),
            CONSTRAINT fk_traces_workspace
                FOREIGN KEY (workspace_id, tenant_id)
                REFERENCES workspaces (id, tenant_id) ON DELETE CASCADE,
            CONSTRAINT fk_traces_run
                FOREIGN KEY (run_id, tenant_id)
                REFERENCES runs (id, tenant_id) ON DELETE CASCADE
        )
        """
    )
    op.execute("CREATE INDEX ix_traces_run_id ON traces (run_id)")
    op.execute("CREATE INDEX ix_traces_workspace_id ON traces (workspace_id)")

    op.execute(
        """
        CREATE TABLE spans (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            trace_id UUID NOT NULL,
            batch_id UUID NOT NULL,
            parent_span_id UUID,
            provider_span_id TEXT,
            name TEXT NOT NULL,
            span_kind span_kind NOT NULL,
            status span_status NOT NULL DEFAULT 'ok',
            error_message TEXT,
            started_at TIMESTAMPTZ NOT NULL,
            ended_at TIMESTAMPTZ,
            model_version_id UUID,
            retrieval_config_version_id UUID,
            tool_definition_version_id UUID,
            workflow_version_id UUID,
            attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
            input_artifact_version_id UUID,
            output_artifact_version_id UUID,
            token_count_input INTEGER,
            token_count_output INTEGER,
            cost_amount NUMERIC,
            cost_currency TEXT,
            created_by UUID NOT NULL REFERENCES users (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_spans_id_tenant UNIQUE (id, tenant_id),
            CONSTRAINT fk_spans_trace
                FOREIGN KEY (trace_id, tenant_id)
                REFERENCES traces (id, tenant_id) ON DELETE CASCADE,
            CONSTRAINT fk_spans_parent_span
                FOREIGN KEY (parent_span_id, tenant_id)
                REFERENCES spans (id, tenant_id),
            CONSTRAINT fk_spans_model_version
                FOREIGN KEY (model_version_id, tenant_id)
                REFERENCES versioned_resource_versions (id, tenant_id),
            CONSTRAINT fk_spans_retrieval_config_version
                FOREIGN KEY (retrieval_config_version_id, tenant_id)
                REFERENCES versioned_resource_versions (id, tenant_id),
            CONSTRAINT fk_spans_tool_definition_version
                FOREIGN KEY (tool_definition_version_id, tenant_id)
                REFERENCES versioned_resource_versions (id, tenant_id),
            CONSTRAINT fk_spans_workflow_version
                FOREIGN KEY (workflow_version_id, tenant_id)
                REFERENCES versioned_resource_versions (id, tenant_id),
            CONSTRAINT fk_spans_input_artifact_version
                FOREIGN KEY (input_artifact_version_id, tenant_id)
                REFERENCES artifact_versions (id, tenant_id),
            CONSTRAINT fk_spans_output_artifact_version
                FOREIGN KEY (output_artifact_version_id, tenant_id)
                REFERENCES artifact_versions (id, tenant_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_spans_trace_id ON spans (trace_id)")
    op.execute("CREATE INDEX ix_spans_parent_span_id ON spans (parent_span_id)")
    # Lets a repeated ingestion batch replay its own idempotency result
    # by re-selecting exactly the rows it created (adapters/idempotency_sql.py).
    op.execute("CREATE INDEX ix_spans_batch_id ON spans (batch_id)")
    # Lets a batch resolve "does this provider span id already exist in
    # this trace" without scanning; NULL provider ids are unconstrained.
    op.execute(
        "CREATE UNIQUE INDEX uq_spans_trace_provider_span_id ON spans (trace_id, provider_span_id) "
        "WHERE provider_span_id IS NOT NULL"
    )

    # Immutability: a finalized trace's own row can never be updated
    # again, matching forbid_finalized_snapshot_mutation exactly.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_finalized_trace_mutation() RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status = 'finalized' THEN
                RAISE EXCEPTION 'trace % is immutable after finalization', OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_forbid_finalized_trace_mutation
        BEFORE UPDATE ON traces
        FOR EACH ROW EXECUTE FUNCTION forbid_finalized_trace_mutation()
        """
    )

    # A span may only be inserted while its trace is still ingesting,
    # its parent (if any) must belong to the same trace, and a span may
    # never be its own parent — the structural-integrity rules
    # Milestone 5 requires beyond what a composite tenant FK alone
    # guarantees (same tenant, not same trace).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_span_insert() RETURNS TRIGGER AS $$
        DECLARE
            trace_status_value trace_status;
            parent_trace_id UUID;
        BEGIN
            SELECT status INTO trace_status_value FROM traces WHERE id = NEW.trace_id;
            IF trace_status_value IS DISTINCT FROM 'ingesting' THEN
                RAISE EXCEPTION 'trace % is not accepting new spans', NEW.trace_id;
            END IF;
            IF NEW.parent_span_id IS NOT NULL THEN
                IF NEW.parent_span_id = NEW.id THEN
                    RAISE EXCEPTION 'span % cannot be its own parent', NEW.id;
                END IF;
                SELECT trace_id INTO parent_trace_id FROM spans WHERE id = NEW.parent_span_id;
                IF parent_trace_id IS DISTINCT FROM NEW.trace_id THEN
                    RAISE EXCEPTION 'span % parent must belong to the same trace', NEW.id;
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validate_span_insert
        BEFORE INSERT ON spans
        FOR EACH ROW EXECUTE FUNCTION validate_span_insert()
        """
    )

    _enable_rls("traces")
    _enable_rls("spans")

    # UPDATE is required only for the ingesting -> finalized
    # transition; the trigger above blocks every update once finalized.
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON traces TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON spans TO {_APP_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON spans FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON traces FROM {_APP_ROLE}")
    op.execute("DROP TRIGGER IF EXISTS trg_validate_span_insert ON spans")
    op.execute("DROP FUNCTION IF EXISTS validate_span_insert()")
    op.execute("DROP TRIGGER IF EXISTS trg_forbid_finalized_trace_mutation ON traces")
    op.execute("DROP FUNCTION IF EXISTS forbid_finalized_trace_mutation()")
    op.execute("DROP TABLE IF EXISTS spans")
    op.execute("DROP TABLE IF EXISTS traces")
    op.execute("DROP TYPE IF EXISTS span_status")
    op.execute("DROP TYPE IF EXISTS span_kind")
    op.execute("DROP TYPE IF EXISTS trace_status")
