"""Bulk import of test cases: valid CSV and JSONL, and the
all-or-nothing rejection contract for any invalid row.

Export and round-trip coverage lives in ``test_dataset_export.py``.
"""

from __future__ import annotations

import json

from dataset_fixtures import (
    BuildContext,
    CreateTenant,
    CreateUser,
    bootstrap_dataset,
)
from evalforge_api.application import dataset_import_service
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


async def test_a_valid_csv_import_commits_every_row(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    fixture = await _dataset(
        evaluation_repositories, create_tenant, create_user, build_tenant_context
    )
    outcome = await dataset_import_service.import_test_cases(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        document=_VALID_CSV,
        import_format="csv",
        repositories=evaluation_repositories,
    )
    assert outcome.committed is True
    assert outcome.import_batch_id is not None
    assert [record.row_index for record in outcome.records] == [1, 2]
    assert all(record.success and record.test_case_id for record in outcome.records)

    cases = await evaluation_repositories.datasets.list_test_cases(
        tenant_id=fixture.tenant_id, dataset_id=fixture.dataset_id, status=None
    )
    assert {case.external_key for case in cases} == {"case-1", "case-2"}
    assert {case.source for case in cases} == {"imported"}
    assert {case.import_batch_id for case in cases} == {outcome.import_batch_id}


async def test_a_valid_jsonl_import_commits_every_row(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    fixture = await _dataset(
        evaluation_repositories, create_tenant, create_user, build_tenant_context
    )
    outcome = await dataset_import_service.import_test_cases(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        document=_VALID_JSONL,
        import_format="jsonl",
        repositories=evaluation_repositories,
    )
    assert outcome.committed is True

    versions = await evaluation_repositories.datasets.list_latest_versions_for_dataset(
        tenant_id=fixture.tenant_id, dataset_id=fixture.dataset_id
    )
    inputs = {json.dumps(version.content["input"], sort_keys=True) for version in versions}
    assert inputs == {'"What is 2 + 2?"', '{"question": "3 + 3"}'}
    assert all(version.version_number == 1 for version in versions)
    assert all(version.dedup_hash for version in versions)


async def test_one_invalid_row_rejects_the_entire_import_and_writes_nothing(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    fixture = await _dataset(
        evaluation_repositories, create_tenant, create_user, build_tenant_context
    )
    document = (
        '{"input": "good row one"}\n'
        '{"expected_output": "missing an input"}\n'
        '{"input": "good row three"}\n'
    )
    outcome = await dataset_import_service.import_test_cases(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        document=document,
        import_format="jsonl",
        repositories=evaluation_repositories,
    )

    assert outcome.committed is False
    assert outcome.import_batch_id is None
    assert [(record.row_index, record.success) for record in outcome.records] == [
        (1, True),
        (2, False),
        (3, True),
    ]
    failure = outcome.records[1]
    assert failure.error is not None
    assert "input" in failure.error

    cases = await evaluation_repositories.datasets.list_test_cases(
        tenant_id=fixture.tenant_id, dataset_id=fixture.dataset_id, status=None
    )
    assert cases == ()


async def test_malformed_json_reports_the_offending_line_number(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    fixture = await _dataset(
        evaluation_repositories, create_tenant, create_user, build_tenant_context
    )
    outcome = await dataset_import_service.import_test_cases(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        document='{"input": "fine"}\nnot-json-at-all\n',
        import_format="jsonl",
        repositories=evaluation_repositories,
    )
    assert outcome.committed is False
    assert outcome.records[1].row_index == 2
    assert outcome.records[1].error is not None
    assert "JSON" in outcome.records[1].error


async def test_a_csv_row_with_unparsable_metadata_is_reported_not_raised(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    fixture = await _dataset(
        evaluation_repositories, create_tenant, create_user, build_tenant_context
    )
    document = "input,metadata\ngood,{}\nalso good,not-json\n"
    outcome = await dataset_import_service.import_test_cases(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        document=document,
        import_format="csv",
        repositories=evaluation_repositories,
    )
    assert outcome.committed is False
    assert outcome.records[0].success is True
    assert outcome.records[1].success is False
    assert outcome.records[1].error is not None
    assert "metadata" in outcome.records[1].error


async def test_an_empty_document_is_rejected_rather_than_silently_committing_nothing(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    fixture = await _dataset(
        evaluation_repositories, create_tenant, create_user, build_tenant_context
    )
    outcome = await dataset_import_service.import_test_cases(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        document="",
        import_format="jsonl",
        repositories=evaluation_repositories,
    )
    assert outcome.committed is False
    assert outcome.records == ()
