"""Dataset and test-case management: mutable dataset metadata,
lifecycle and provenance columns, and the duplicate-detection hash.

Additive only. The Milestone 4 immutability boundary is unchanged:
``test_case_versions`` and finalized ``dataset_snapshots`` remain
append-only, and no table anywhere gains DELETE. What changes is that
a dataset's and a test case's *mutable* attributes — name, description,
tags, metadata, status, archival timestamp — become updatable, which
requires an UPDATE grant on those two tables. Content still only ever
changes by creating a new ``test_case_versions`` row.

Provenance columns record where a dataset or test case came from
(manual authoring, an import batch, or a clone of another dataset or
snapshot) using composite ``(id, tenant_id)`` foreign keys, so a
cross-tenant lineage reference remains impossible to insert.

``dedup_hash`` backfill: every row that predates this migration gets
the ``''`` column default and would otherwise never participate in
duplicate detection. Reproducing ``domain.duplicate_detection``'s
normalization (Unicode case-folding, recursive-sort-keys canonical
JSON) as raw SQL would be a second, drift-prone hashing
implementation — exactly what ``docs/REPRODUCIBILITY_CONTRACT.md``
forbids. Instead, ``_backfill_legacy_dedup_hashes`` below calls that
exact domain function from within the migration, so there is still
only one hashing implementation in the codebase. A row whose stored
content cannot be read as valid ``TestCaseContent`` (there is no such
row today, but a migration must not assume that) is left with an
empty hash rather than aborting the whole migration.

Revision ID: 0009_dataset_test_case_mgmt
Revises: 0008_evidence_idempotency
Create Date: 2026-08-17
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_dataset_test_case_mgmt"
down_revision: str | None = "0008_evidence_idempotency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "evalforge_app"


def _backfill_legacy_dedup_hashes() -> None:
    from evalforge_api.domain.duplicate_detection import compute_dedup_hash
    from evalforge_api.domain.test_case_content import (
        InvalidTestCaseContentError,
        TestCaseContent,
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, content FROM test_case_versions WHERE dedup_hash = ''")
    ).fetchall()
    for row in rows:
        content = row.content if isinstance(row.content, dict) else json.loads(row.content)
        try:
            dedup_hash = compute_dedup_hash(TestCaseContent.from_json_dict(content))
        except InvalidTestCaseContentError:
            continue
        bind.execute(
            sa.text("UPDATE test_case_versions SET dedup_hash = :hash WHERE id = :id"),
            {"hash": dedup_hash, "id": row.id},
        )


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE datasets
            ADD COLUMN description TEXT,
            ADD COLUMN tags JSONB NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            ADD COLUMN updated_by UUID REFERENCES users (id),
            ADD COLUMN archived_at TIMESTAMPTZ,
            ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'
                CHECK (source IN ('manual', 'cloned')),
            ADD COLUMN cloned_from_dataset_id UUID,
            ADD COLUMN cloned_from_snapshot_id UUID
        """
    )
    # Clone lineage is tenant-consistent by construction: the composite
    # foreign keys below can only resolve to a row owned by the same
    # tenant as the referencing dataset.
    op.execute(
        """
        ALTER TABLE datasets
            ADD CONSTRAINT fk_datasets_cloned_from_dataset
                FOREIGN KEY (cloned_from_dataset_id, tenant_id)
                REFERENCES datasets (id, tenant_id),
            ADD CONSTRAINT fk_datasets_cloned_from_snapshot
                FOREIGN KEY (cloned_from_snapshot_id, tenant_id)
                REFERENCES dataset_snapshots (id, tenant_id)
        """
    )
    op.execute("CREATE INDEX ix_datasets_status ON datasets (tenant_id, status)")

    op.execute(
        """
        ALTER TABLE test_cases
            ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            ADD COLUMN updated_by UUID REFERENCES users (id),
            ADD COLUMN archived_at TIMESTAMPTZ,
            ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'
                CHECK (source IN ('manual', 'imported', 'cloned')),
            ADD COLUMN source_test_case_id UUID,
            ADD COLUMN import_batch_id UUID
        """
    )
    op.execute(
        """
        ALTER TABLE test_cases
            ADD CONSTRAINT fk_test_cases_source_test_case
                FOREIGN KEY (source_test_case_id, tenant_id)
                REFERENCES test_cases (id, tenant_id)
        """
    )
    op.execute("CREATE INDEX ix_test_cases_import_batch_id ON test_cases (import_batch_id)")

    # Duplicate detection is dataset-scoped and structural (see
    # evalforge_api.domain.duplicate_detection). The default exists
    # only so the NOT NULL constraint can be added to a table that may
    # already hold rows; every insert from application code supplies a
    # real hash.
    op.execute("ALTER TABLE test_case_versions ADD COLUMN dedup_hash TEXT NOT NULL DEFAULT ''")
    op.execute(
        "CREATE INDEX ix_test_case_versions_dedup_hash "
        "ON test_case_versions (test_case_id, dedup_hash)"
    )
    _backfill_legacy_dedup_hashes()

    # Mutable-metadata tables only. test_case_versions and
    # dataset_snapshot_items remain INSERT/SELECT, and dataset_snapshots
    # keeps the pre-existing UPDATE grant that the trigger already
    # limits to the single draft -> finalized transition.
    op.execute(f"GRANT UPDATE ON datasets TO {_APP_ROLE}")
    op.execute(f"GRANT UPDATE ON test_cases TO {_APP_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ON test_cases FROM {_APP_ROLE}")
    op.execute(f"REVOKE UPDATE ON datasets FROM {_APP_ROLE}")

    op.execute("DROP INDEX IF EXISTS ix_test_case_versions_dedup_hash")
    op.execute("ALTER TABLE test_case_versions DROP COLUMN IF EXISTS dedup_hash")

    op.execute("DROP INDEX IF EXISTS ix_test_cases_import_batch_id")
    op.execute("ALTER TABLE test_cases DROP CONSTRAINT IF EXISTS fk_test_cases_source_test_case")
    op.execute(
        """
        ALTER TABLE test_cases
            DROP COLUMN IF EXISTS import_batch_id,
            DROP COLUMN IF EXISTS source_test_case_id,
            DROP COLUMN IF EXISTS source,
            DROP COLUMN IF EXISTS archived_at,
            DROP COLUMN IF EXISTS updated_by,
            DROP COLUMN IF EXISTS updated_at
        """
    )

    op.execute("DROP INDEX IF EXISTS ix_datasets_status")
    op.execute("ALTER TABLE datasets DROP CONSTRAINT IF EXISTS fk_datasets_cloned_from_snapshot")
    op.execute("ALTER TABLE datasets DROP CONSTRAINT IF EXISTS fk_datasets_cloned_from_dataset")
    op.execute(
        """
        ALTER TABLE datasets
            DROP COLUMN IF EXISTS cloned_from_snapshot_id,
            DROP COLUMN IF EXISTS cloned_from_dataset_id,
            DROP COLUMN IF EXISTS source,
            DROP COLUMN IF EXISTS archived_at,
            DROP COLUMN IF EXISTS updated_by,
            DROP COLUMN IF EXISTS updated_at,
            DROP COLUMN IF EXISTS metadata,
            DROP COLUMN IF EXISTS tags,
            DROP COLUMN IF EXISTS description
        """
    )
