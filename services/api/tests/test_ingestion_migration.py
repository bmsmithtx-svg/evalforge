from __future__ import annotations

import asyncpg

from evalforge_api.settings import Settings

_EXPECTED_TABLES = (
    "runs",
    "run_tool_versions",
    "traces",
    "spans",
    "run_evidence_artifacts",
    "idempotency_records",
)

_EXPECTED_TENANT_CONSISTENT_FOREIGN_KEYS = (
    "fk_runs_workspace",
    "fk_runs_evaluation_target",
    "fk_runs_model_version",
    "fk_runs_prompt_version",
    "fk_runs_retrieval_config_version",
    "fk_runs_workflow_version",
    "fk_runs_pricing_version",
    "fk_run_tool_versions_run",
    "fk_run_tool_versions_tool_version",
    "fk_traces_workspace",
    "fk_traces_run",
    "fk_spans_trace",
    "fk_spans_parent_span",
    "fk_spans_model_version",
    "fk_spans_retrieval_config_version",
    "fk_spans_tool_definition_version",
    "fk_spans_workflow_version",
    "fk_spans_input_artifact_version",
    "fk_spans_output_artifact_version",
    "fk_run_evidence_artifacts_run",
    "fk_run_evidence_artifacts_trace",
    "fk_run_evidence_artifacts_artifact_version",
)

_TABLES_WITH_UPDATE_GRANT = {"runs", "traces"}


async def test_migration_head_revision_is_the_last_ingestion_migration(
    test_settings: Settings,
) -> None:
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        row = await connection.fetchrow("SELECT version_num FROM alembic_version")
    finally:
        await connection.close()
    assert row is not None
    assert row["version_num"] == "0008_evidence_idempotency"


async def test_every_ingestion_table_exists(test_settings: Settings) -> None:
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        rows = await connection.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
    finally:
        await connection.close()
    existing = {row["table_name"] for row in rows}
    missing = set(_EXPECTED_TABLES) - existing
    assert not missing, f"missing ingestion tables: {missing}"


async def test_composite_tenant_consistent_foreign_keys_exist(test_settings: Settings) -> None:
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


async def test_idempotency_records_cascades_from_tenant_deletion(test_settings: Settings) -> None:
    """``idempotency_records`` is not a child of any other Milestone 5
    table (it references ``tenants`` directly), so this is checked
    separately from the composite-FK list above."""
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        row = await connection.fetchrow(
            "SELECT confdeltype FROM pg_constraint "
            "WHERE conname = 'idempotency_records_tenant_id_fkey'"
        )
    finally:
        await connection.close()
    assert row is not None
    assert row["confdeltype"] == b"c"  # ON DELETE CASCADE ("char" pseudo-type, returned as bytes)


async def test_row_level_security_is_enabled_and_forced_on_every_ingestion_table(
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


async def test_app_role_has_no_delete_grant_on_any_ingestion_table(test_settings: Settings) -> None:
    connection = await asyncpg.connect(dsn=str(test_settings.database_url))
    try:
        rows = await connection.fetch(
            """
            SELECT table_name FROM information_schema.role_table_grants
            WHERE grantee = 'evalforge_app'
              AND table_name = ANY($1::text[])
              AND privilege_type = 'DELETE'
            """,
            list(_EXPECTED_TABLES),
        )
    finally:
        await connection.close()
    assert rows == []


async def test_app_role_update_grant_is_limited_to_runs_and_traces(test_settings: Settings) -> None:
    """Only runs and traces support the active -> terminal/finalized
    transition; every other ingestion table is insert-only."""
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
    assert {row["table_name"] for row in rows} == _TABLES_WITH_UPDATE_GRANT
