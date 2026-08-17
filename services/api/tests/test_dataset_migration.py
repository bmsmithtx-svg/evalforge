from __future__ import annotations

import asyncpg
import pytest

from evalforge_api.settings import Settings

_TOUCHED_TABLES = ("datasets", "test_cases", "test_case_versions", "dataset_snapshots")
_EXPECTED_DATASET_COLUMNS = (
    "description",
    "tags",
    "metadata",
    "updated_at",
    "updated_by",
    "archived_at",
    "source",
    "cloned_from_dataset_id",
    "cloned_from_snapshot_id",
)
_EXPECTED_TEST_CASE_COLUMNS = (
    "updated_at",
    "updated_by",
    "archived_at",
    "source",
    "source_test_case_id",
    "import_batch_id",
)
_EXPECTED_TENANT_CONSISTENT_FOREIGN_KEYS = (
    "fk_datasets_cloned_from_dataset",
    "fk_datasets_cloned_from_snapshot",
    "fk_test_cases_source_test_case",
)
_EXPECTED_INDEXES = (
    "ix_test_case_versions_dedup_hash",
    "ix_test_cases_import_batch_id",
    "ix_datasets_status",
)
_TABLES_WITH_UPDATE_GRANT = {"datasets", "test_cases", "dataset_snapshots"}


async def _columns(settings: Settings, table: str) -> set[str]:
    connection = await asyncpg.connect(dsn=str(settings.database_url))
    try:
        rows = await connection.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = $1",
            table,
        )
    finally:
        await connection.close()
    return {row["column_name"] for row in rows}


async def test_migration_head_revision_is_the_dataset_management_migration(
    test_settings: Settings,
) -> None:
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        row = await connection.fetchrow("SELECT version_num FROM alembic_version")
    finally:
        await connection.close()
    assert row is not None
    assert row["version_num"] == "0009_dataset_test_case_mgmt"


async def test_every_new_dataset_column_exists(test_settings: Settings) -> None:
    columns = await _columns(test_settings, "datasets")
    missing = set(_EXPECTED_DATASET_COLUMNS) - columns
    assert not missing, f"missing dataset columns: {missing}"


async def test_every_new_test_case_column_exists(test_settings: Settings) -> None:
    columns = await _columns(test_settings, "test_cases")
    missing = set(_EXPECTED_TEST_CASE_COLUMNS) - columns
    assert not missing, f"missing test-case columns: {missing}"


async def test_test_case_versions_gained_the_dedup_hash_column(test_settings: Settings) -> None:
    assert "dedup_hash" in await _columns(test_settings, "test_case_versions")


async def test_new_lineage_foreign_keys_are_tenant_consistent(test_settings: Settings) -> None:
    """Each clone/import provenance reference is a composite
    ``(id, tenant_id)`` foreign key, so a cross-tenant provenance
    reference cannot be inserted at all."""
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        rows = await connection.fetch(
            "SELECT conname, array_length(conkey, 1) AS column_count FROM pg_constraint "
            "WHERE conname = ANY($1::text[])",
            list(_EXPECTED_TENANT_CONSISTENT_FOREIGN_KEYS),
        )
    finally:
        await connection.close()
    by_name = {row["conname"]: row for row in rows}
    assert set(by_name) == set(_EXPECTED_TENANT_CONSISTENT_FOREIGN_KEYS)
    for name, row in by_name.items():
        assert row["column_count"] == 2, f"{name} is not a composite (id, tenant_id) key"


async def test_every_new_index_exists(test_settings: Settings) -> None:
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        rows = await connection.fetch(
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' "
            "AND indexname = ANY($1::text[])",
            list(_EXPECTED_INDEXES),
        )
    finally:
        await connection.close()
    assert {row["indexname"] for row in rows} == set(_EXPECTED_INDEXES)


@pytest.mark.parametrize(
    ("table", "column", "allowed"),
    [
        ("datasets", "source", {"manual", "cloned"}),
        ("test_cases", "source", {"manual", "imported", "cloned"}),
    ],
)
async def test_source_column_is_constrained_to_the_documented_values(
    test_settings: Settings, table: str, column: str, allowed: set[str]
) -> None:
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        rows = await connection.fetch(
            """
            SELECT pg_get_constraintdef(c.oid) AS definition
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            WHERE t.relname = $1 AND c.contype = 'c'
            """,
            table,
        )
    finally:
        await connection.close()
    definitions = [row["definition"] for row in rows if column in row["definition"]]
    assert definitions, f"no CHECK constraint found on {table}.{column}"
    combined = " ".join(definitions)
    for value in allowed:
        assert f"'{value}'" in combined


async def test_row_level_security_is_still_enabled_and_forced_on_touched_tables(
    test_settings: Settings,
) -> None:
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        rows = await connection.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class WHERE relname = ANY($1::text[]) AND relkind = 'r'
            """,
            list(_TOUCHED_TABLES),
        )
    finally:
        await connection.close()
    by_name = {row["relname"]: row for row in rows}
    assert set(by_name) == set(_TOUCHED_TABLES)
    for name, row in by_name.items():
        assert row["relrowsecurity"] is True, f"{name} does not have RLS enabled"
        assert row["relforcerowsecurity"] is True, f"{name} does not force RLS on its owner"


async def test_update_grant_covers_only_the_mutable_metadata_tables(
    test_settings: Settings,
) -> None:
    """``datasets`` and ``test_cases`` hold mutable attributes;
    ``dataset_snapshots`` keeps its pre-existing, trigger-limited
    finalize grant; ``test_case_versions`` stays append-only."""
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        rows = await connection.fetch(
            """
            SELECT table_name FROM information_schema.role_table_grants
            WHERE grantee = 'evalforge_app'
              AND table_name = ANY($1::text[])
              AND privilege_type = 'UPDATE'
            """,
            list(_TOUCHED_TABLES),
        )
    finally:
        await connection.close()
    assert {row["table_name"] for row in rows} == _TABLES_WITH_UPDATE_GRANT


async def test_no_delete_grant_was_introduced_anywhere(test_settings: Settings) -> None:
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        rows = await connection.fetch(
            """
            SELECT table_name FROM information_schema.role_table_grants
            WHERE grantee = 'evalforge_app' AND privilege_type = 'DELETE'
            """
        )
    finally:
        await connection.close()
    assert rows == []


async def test_the_application_role_still_cannot_update_test_case_versions(
    test_settings: Settings,
) -> None:
    """Least privilege, verified against the live role rather than the
    grant catalogue alone: immutable content cannot be rewritten."""
    connection = await asyncpg.connect(dsn=str(test_settings.app_database_url))
    try:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await connection.execute("UPDATE test_case_versions SET content_hash = 'tampered'")
    finally:
        await connection.close()
