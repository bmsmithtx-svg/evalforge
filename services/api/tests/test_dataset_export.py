"""Dataset export: documented schemas, embedded provenance,
deterministic output, and an export that re-imports unchanged.
"""

from __future__ import annotations

import json

from dataset_fixtures import (
    BuildContext,
    CreateTenant,
    CreateUser,
    add_test_case,
    bootstrap_dataset,
)
from evalforge_api.application import dataset_export_service, dataset_import_service
from evalforge_api.domain.export_formatting import CSV_EXPORT_COLUMNS, EXPORT_FORMAT_VERSION
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories

_VALID_CSV = (
    "external_key,input,expected_output,tags,category,difficulty,metadata\n"
    'case-1,What is 2 + 2?,4,"math,arithmetic",math,easy,"{""owner"": ""qa""}"\n'
    "case-2,What is 3 + 3?,6,math,math,easy,\n"
)
_VALID_JSONL = (
    '{"external_key": "case-1", "input": "What is 2 + 2?", "expected_output": "4", '
    '"tags": ["math"]}\n'
    '{"external_key": "case-2", "input": {"question": "3 + 3"}, "expected_output": "6"}\n'
)


async def _dataset(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
    slug: str = "tenant-a",
    email: str = "a@example.com",
):  # noqa: ANN202 -- returns the shared DatasetFixture dataclass
    return await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug=slug,
        email=email,
    )


async def test_jsonl_export_carries_the_documented_provenance_header(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    fixture = await _dataset(
        evaluation_repositories, create_tenant, create_user, build_tenant_context
    )
    await add_test_case(
        fixture=fixture,
        repositories=evaluation_repositories,
        content={"input": "exported question", "expected_output": "answer"},
        external_key="case-1",
    )

    document = await dataset_export_service.export_dataset(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        snapshot_id=None,
        export_format="jsonl",
        repositories=evaluation_repositories,
    )
    lines = document.strip().split("\n")
    header = json.loads(lines[0])["evalforge_export"]
    assert header["format_version"] == EXPORT_FORMAT_VERSION
    assert header["dataset_id"] == str(fixture.dataset_id)
    assert header["snapshot_id"] is None
    assert header["snapshot_content_hash"] is None
    assert header["item_count"] == 1

    body = json.loads(lines[1])
    assert body["input"] == "exported question"
    assert body["expected_output"] == "answer"
    assert body["external_key"] == "case-1"
    assert body["version_number"] == 1


async def test_csv_export_uses_the_documented_column_schema(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    fixture = await _dataset(
        evaluation_repositories, create_tenant, create_user, build_tenant_context
    )
    await add_test_case(
        fixture=fixture,
        repositories=evaluation_repositories,
        content={"input": "csv question", "expected_output": "csv answer", "tags": ["alpha"]},
        external_key="case-1",
    )
    document = await dataset_export_service.export_dataset(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        snapshot_id=None,
        export_format="csv",
        repositories=evaluation_repositories,
    )
    header, first_row = document.strip().split("\n")[:2]
    assert header.split(",") == list(CSV_EXPORT_COLUMNS)
    assert "csv question" in first_row
    assert str(fixture.dataset_id) in first_row


async def test_export_is_byte_identical_across_repeated_calls(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    fixture = await _dataset(
        evaluation_repositories, create_tenant, create_user, build_tenant_context
    )
    for index in range(4):
        await add_test_case(
            fixture=fixture,
            repositories=evaluation_repositories,
            content={"input": f"question {index}"},
            external_key=f"case-{index}",
        )
    first = await dataset_export_service.export_dataset(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        snapshot_id=None,
        export_format="jsonl",
        repositories=evaluation_repositories,
    )
    second = await dataset_export_service.export_dataset(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        snapshot_id=None,
        export_format="jsonl",
        repositories=evaluation_repositories,
    )
    assert first == second


async def test_a_csv_export_round_trips_back_through_import(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    """The provenance columns an export adds are ignored on re-import,
    so exported content reproduces equivalent test cases."""
    source = await _dataset(
        evaluation_repositories, create_tenant, create_user, build_tenant_context
    )
    await dataset_import_service.import_test_cases(
        context=source.context,
        dataset_id=source.dataset_id,
        document=_VALID_CSV,
        import_format="csv",
        repositories=evaluation_repositories,
    )
    exported = await dataset_export_service.export_dataset(
        context=source.context,
        dataset_id=source.dataset_id,
        snapshot_id=None,
        export_format="csv",
        repositories=evaluation_repositories,
    )

    from evalforge_api.application import dataset_service

    target = await dataset_service.create_dataset(
        context=source.context,
        workspace_id=source.workspace_id,
        name="Round trip",
        repositories=evaluation_repositories,
    )
    outcome = await dataset_import_service.import_test_cases(
        context=source.context,
        dataset_id=target.id,
        document=exported,
        import_format="csv",
        repositories=evaluation_repositories,
    )
    assert outcome.committed is True

    original = await evaluation_repositories.datasets.list_latest_versions_for_dataset(
        tenant_id=source.tenant_id, dataset_id=source.dataset_id
    )
    reimported = await evaluation_repositories.datasets.list_latest_versions_for_dataset(
        tenant_id=source.tenant_id, dataset_id=target.id
    )
    assert len(reimported) == len(original) == 2
    assert {version.dedup_hash for version in reimported} == {
        version.dedup_hash for version in original
    }
    assert {version.content_hash for version in reimported} == {
        version.content_hash for version in original
    }


async def test_exporting_a_finalized_snapshot_records_its_content_hash(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    from evalforge_api.application import snapshot_service

    fixture = await _dataset(
        evaluation_repositories, create_tenant, create_user, build_tenant_context
    )
    version = await add_test_case(
        fixture=fixture, repositories=evaluation_repositories, content={"input": "frozen question"}
    )
    snapshot = await snapshot_service.create_draft_snapshot(
        context=fixture.context, dataset_id=fixture.dataset_id, repositories=evaluation_repositories
    )
    await snapshot_service.add_test_case_version(
        context=fixture.context,
        snapshot_id=snapshot.id,
        test_case_version_id=version.id,
        sequence_index=0,
        repositories=evaluation_repositories,
    )
    finalized = await snapshot_service.finalize_snapshot(
        context=fixture.context, snapshot_id=snapshot.id, repositories=evaluation_repositories
    )

    document = await dataset_export_service.export_dataset(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        snapshot_id=snapshot.id,
        export_format="jsonl",
        repositories=evaluation_repositories,
    )
    header = json.loads(document.strip().split("\n")[0])["evalforge_export"]
    assert header["snapshot_id"] == str(snapshot.id)
    assert header["snapshot_content_hash"] == finalized.content_hash
    body = json.loads(document.strip().split("\n")[1])
    assert body["sequence_index"] == 0
