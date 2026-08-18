"""Regression coverage for the Milestone 6 correction-pass backfill of
``test_case_versions.dedup_hash``.

Migration ``0009_dataset_test_case_mgmt`` adds ``dedup_hash`` with a
``NOT NULL DEFAULT ''``. A row that existed before this migration ran
would otherwise be stuck at ``''`` forever and never participate in
duplicate detection. This test exercises the real thing: it downgrades
the live test database to ``0008_evidence_idempotency`` (dropping the
column entirely), inserts a version row shaped exactly like the
pre-Milestone-6 schema, upgrades back to head, and proves the
migration's backfill computed the same fingerprint the domain function
would and that duplicate detection now recognizes it.
"""

from __future__ import annotations

import json
import subprocess
import sys

import asyncpg

from conftest import API_DIR, _settings_env
from dataset_fixtures import BuildContext, CreateTenant, CreateUser
from evalforge_api.application import (
    dataset_service,
    duplicate_detection_service,
    test_case_service,
    workspace_service,
)
from evalforge_api.domain.duplicate_detection import compute_dedup_hash
from evalforge_api.domain.enums import TenantRole
from evalforge_api.domain.hashing import (
    CANONICALIZATION_VERSION,
    HASH_ALGORITHM,
    hash_canonical_content,
)
from evalforge_api.domain.test_case_content import TestCaseContent
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.settings import Settings

_LEGACY_CONTENT = {"input": "  What   IS the   Refund Window?  "}


def _downgrade_to_0008(settings: Settings) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0008_evidence_idempotency"],
        cwd=API_DIR,
        env=_settings_env(settings),
        check=True,
        capture_output=True,
        text=True,
    )


def _upgrade_to_head(settings: Settings) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        env=_settings_env(settings),
        check=True,
        capture_output=True,
        text=True,
    )


async def test_a_pre_0009_test_case_version_receives_a_correct_backfilled_dedup_hash(
    test_settings_session: Settings,
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    tenant_id = await create_tenant("dedup-backfill")
    user_id = await create_user("backfill@example.com")
    admin_context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.TENANT_ADMIN
    )
    workspace = await workspace_service.create_workspace(
        context=admin_context, slug="ws", name="Workspace", repositories=evaluation_repositories
    )
    engineer_context = build_tenant_context(
        tenant_id=tenant_id, user_id=user_id, role=TenantRole.EVALUATION_ENGINEER
    )
    dataset = await dataset_service.create_dataset(
        context=engineer_context,
        workspace_id=workspace.id,
        name="Pre-existing dataset",
        repositories=evaluation_repositories,
    )
    test_case = await test_case_service.create_test_case(
        context=engineer_context,
        dataset_id=dataset.id,
        external_key=None,
        repositories=evaluation_repositories,
    )

    try:
        # Drop back to the schema this row would have lived under before
        # Milestone 6: no dedup_hash column exists at all.
        _downgrade_to_0008(test_settings_session)

        admin_connection = await asyncpg.connect(dsn=str(test_settings_session.database_url))
        try:
            legacy_version_id = await admin_connection.fetchval(
                """
                INSERT INTO test_case_versions (
                    tenant_id, test_case_id, version_number, content, content_hash,
                    hash_algorithm, canonicalization_version, created_by
                )
                VALUES ($1, $2, 1, $3::jsonb, $4, $5, $6, $7)
                RETURNING id
                """,
                tenant_id,
                test_case.id,
                json.dumps(_LEGACY_CONTENT),
                hash_canonical_content(_LEGACY_CONTENT),
                HASH_ALGORITHM,
                CANONICALIZATION_VERSION,
                user_id,
            )
        finally:
            await admin_connection.close()

        # Back to head: the backfill in 0009's upgrade() must find this
        # row (dedup_hash = '') and compute its real fingerprint.
        _upgrade_to_head(test_settings_session)

        verify_connection = await asyncpg.connect(dsn=str(test_settings_session.database_url))
        try:
            backfilled_hash = await verify_connection.fetchval(
                "SELECT dedup_hash FROM test_case_versions WHERE id = $1", legacy_version_id
            )
        finally:
            await verify_connection.close()
    finally:
        # However the test ends, the shared database must come back to
        # head for every other test in this session.
        _upgrade_to_head(test_settings_session)

    expected_hash = compute_dedup_hash(TestCaseContent.from_json_dict(_LEGACY_CONTENT))
    assert backfilled_hash == expected_hash
    assert backfilled_hash != ""

    # Functional proof, not just a column value: a new, differently
    # formatted but structurally-identical submission is now recognized
    # as a duplicate of the pre-migration row.
    duplicates = await duplicate_detection_service.check_for_duplicates(
        context=engineer_context,
        dataset_id=dataset.id,
        content=TestCaseContent(input="what is the refund window?"),
        repositories=evaluation_repositories,
    )
    assert duplicates == (test_case.id,)
