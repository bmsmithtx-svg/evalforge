"""Ingestion domain: run/trace evidence-artifact linkage and durable
idempotency records.

``run_evidence_artifacts`` links a Milestone 4 artifact version to a
run or trace as supporting evidence (a span's own direct
input/output-artifact columns cover the common per-span case).
``idempotency_records`` is the durable, race-safe source of truth for
"same key, same request -> reuse; same key, different request ->
conflict" — see docs/THREAT_MODEL.md ("Replay attacks") and
``evalforge_api.adapters.idempotency_sql``. It is never held only in
Redis or process memory.

Revision ID: 0008_evidence_idempotency
Revises: 0007_ingestion_traces_spans
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008_evidence_idempotency"
down_revision: str | None = "0007_ingestion_traces_spans"
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
        """
        CREATE TABLE run_evidence_artifacts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            run_id UUID,
            trace_id UUID,
            artifact_version_id UUID NOT NULL,
            role TEXT NOT NULL,
            created_by UUID NOT NULL REFERENCES users (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_run_evidence_artifacts_has_owner
                CHECK (run_id IS NOT NULL OR trace_id IS NOT NULL),
            CONSTRAINT fk_run_evidence_artifacts_run
                FOREIGN KEY (run_id, tenant_id)
                REFERENCES runs (id, tenant_id) ON DELETE CASCADE,
            CONSTRAINT fk_run_evidence_artifacts_trace
                FOREIGN KEY (trace_id, tenant_id)
                REFERENCES traces (id, tenant_id) ON DELETE CASCADE,
            CONSTRAINT fk_run_evidence_artifacts_artifact_version
                FOREIGN KEY (artifact_version_id, tenant_id)
                REFERENCES artifact_versions (id, tenant_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_run_evidence_artifacts_run_id ON run_evidence_artifacts (run_id)")
    op.execute(
        "CREATE INDEX ix_run_evidence_artifacts_trace_id ON run_evidence_artifacts (trace_id)"
    )

    # Durable idempotency: the UNIQUE constraint below is the actual
    # race-safety mechanism (see adapters/idempotency_sql.py) — two
    # concurrent requests with the same key can both attempt the
    # insert, but only one commits; the loser's transaction rolls back
    # and the caller re-reads the winning row rather than duplicating
    # evidence.
    op.execute(
        """
        CREATE TABLE idempotency_records (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
            operation TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            request_fingerprint TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id UUID NOT NULL,
            created_by UUID NOT NULL REFERENCES users (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_idempotency_records_tenant_operation_key
                UNIQUE (tenant_id, operation, idempotency_key)
        )
        """
    )

    _enable_rls("run_evidence_artifacts")
    _enable_rls("idempotency_records")

    # Least privilege: no UPDATE or DELETE anywhere in this migration.
    # An idempotency record and an evidence link are both immutable
    # facts from the moment they are recorded — the only supported
    # write is INSERT.
    op.execute(f"GRANT SELECT, INSERT ON run_evidence_artifacts TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON idempotency_records TO {_APP_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON idempotency_records FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON run_evidence_artifacts FROM {_APP_ROLE}")
    op.execute("DROP TABLE IF EXISTS idempotency_records")
    op.execute("DROP TABLE IF EXISTS run_evidence_artifacts")
