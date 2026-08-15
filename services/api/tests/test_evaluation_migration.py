from __future__ import annotations

import asyncpg

from evalforge_api.settings import Settings

_EXPECTED_TABLES = (
    "workspaces",
    "evaluation_targets",
    "versioned_resources",
    "versioned_resource_versions",
    "datasets",
    "test_cases",
    "test_case_versions",
    "dataset_snapshots",
    "dataset_snapshot_items",
    "artifacts",
    "artifact_versions",
)

_EXPECTED_TENANT_CONSISTENT_FOREIGN_KEYS = (
    "fk_evaluation_targets_workspace",
    "fk_versioned_resources_workspace",
    "fk_versioned_resource_versions_resource",
    "fk_versioned_resource_versions_derived_from",
    "fk_datasets_workspace",
    "fk_test_cases_dataset",
    "fk_test_case_versions_test_case",
    "fk_dataset_snapshots_dataset",
    "fk_dataset_snapshot_items_snapshot",
    "fk_dataset_snapshot_items_test_case_version",
    "fk_artifacts_workspace",
    "fk_artifact_versions_artifact",
    "fk_artifact_versions_derived_from",
)


async def test_migration_head_revision_is_the_last_evaluation_domain_migration(
    test_settings: Settings,
) -> None:
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        row = await connection.fetchrow("SELECT version_num FROM alembic_version")
    finally:
        await connection.close()
    assert row is not None
    assert row["version_num"] == "0005_eval_domain_artifacts"


async def test_every_evaluation_domain_table_exists(test_settings: Settings) -> None:
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        rows = await connection.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
    finally:
        await connection.close()
    existing = {row["table_name"] for row in rows}
    missing = set(_EXPECTED_TABLES) - existing
    assert not missing, f"missing evaluation-domain tables: {missing}"


async def test_composite_tenant_consistent_foreign_keys_exist(test_settings: Settings) -> None:
    """Every child-to-parent lineage reference introduced by the
    evaluation-domain migrations is a composite ``(id, tenant_id)``
    foreign key — the database-level guarantee that a cross-tenant
    lineage reference is impossible to insert."""
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        rows = await connection.fetch(
            "SELECT conname FROM pg_constraint WHERE conname = ANY($1::text[])",
            list(_EXPECTED_TENANT_CONSISTENT_FOREIGN_KEYS),
        )
    finally:
        await connection.close()
    found = {row["conname"] for row in rows}
    assert found == set(_EXPECTED_TENANT_CONSISTENT_FOREIGN_KEYS)


async def test_row_level_security_is_enabled_and_forced_on_every_tenant_owned_table(
    test_settings: Settings,
) -> None:
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        rows = await connection.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[]) AND relkind = 'r'
            """,
            list(_EXPECTED_TABLES),
        )
    finally:
        await connection.close()
    by_name = {row["relname"]: row for row in rows}
    assert set(by_name) == set(_EXPECTED_TABLES)
    for name, row in by_name.items():
        assert row["relrowsecurity"] is True, f"{name} does not have RLS enabled"
        assert row["relforcerowsecurity"] is True, f"{name} does not force RLS on its owner"


async def test_app_role_has_no_delete_grant_on_any_evaluation_domain_table(
    test_settings: Settings,
) -> None:
    """No supported application path may hard-delete immutable
    evidence; the least-privilege role never receives DELETE."""
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        rows = await connection.fetch(
            """
            SELECT table_name, privilege_type FROM information_schema.role_table_grants
            WHERE grantee = 'evalforge_app'
              AND table_name = ANY($1::text[])
              AND privilege_type = 'DELETE'
            """,
            list(_EXPECTED_TABLES),
        )
    finally:
        await connection.close()
    assert rows == []


async def test_app_role_has_no_update_grant_except_dataset_snapshots(
    test_settings: Settings,
) -> None:
    """Immutable version and item tables (all but ``dataset_snapshots``,
    which needs UPDATE only for the draft -> finalized transition)
    grant no UPDATE at all — the only supported write is INSERT."""
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        rows = await connection.fetch(
            """
            SELECT table_name FROM information_schema.role_table_grants
            WHERE grantee = 'evalforge_app'
              AND table_name = ANY($1::text[])
              AND privilege_type = 'UPDATE'
            """,
            list(_EXPECTED_TABLES),
        )
    finally:
        await connection.close()
    assert {row["table_name"] for row in rows} == {"dataset_snapshots"}
