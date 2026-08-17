from __future__ import annotations

from uuid import uuid4

from dataset_fixtures import (
    BuildContext,
    CreateTenant,
    CreateUser,
    add_test_case,
    bootstrap_dataset,
)
from evalforge_api.application import dataset_service, duplicate_detection_service
from evalforge_api.domain.test_case_content import TestCaseContent
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


async def test_an_exact_duplicate_within_the_dataset_is_flagged(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    fixture = await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-a",
        email="a@example.com",
    )
    existing = await add_test_case(
        fixture=fixture,
        repositories=evaluation_repositories,
        content={"input": "What is the refund window?"},
    )

    duplicates = await duplicate_detection_service.check_for_duplicates(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        content=TestCaseContent(input="  what IS   the refund window? "),
        repositories=evaluation_repositories,
    )
    assert duplicates == (existing.test_case_id,)


async def test_a_near_miss_is_not_flagged(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    fixture = await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-a",
        email="a@example.com",
    )
    await add_test_case(
        fixture=fixture,
        repositories=evaluation_repositories,
        content={"input": "What is the refund window?"},
    )

    duplicates = await duplicate_detection_service.check_for_duplicates(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        content=TestCaseContent(input="What is the refund policy?"),
        repositories=evaluation_repositories,
    )
    assert duplicates == ()


async def test_a_duplicate_in_a_different_dataset_of_the_same_tenant_is_not_flagged(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    """Duplicate detection is dataset-scoped: the same case may
    legitimately appear in two different datasets."""
    fixture = await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-a",
        email="a@example.com",
    )
    other = await dataset_service.create_dataset(
        context=fixture.context,
        workspace_id=fixture.workspace_id,
        name="Other",
        repositories=evaluation_repositories,
    )
    await add_test_case(
        fixture=fixture,
        repositories=evaluation_repositories,
        content={"input": "shared question"},
        dataset_id=other.id,
    )

    duplicates = await duplicate_detection_service.check_for_duplicates(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        content=TestCaseContent(input="shared question"),
        repositories=evaluation_repositories,
    )
    assert duplicates == ()


async def test_an_archived_test_case_no_longer_counts_as_a_duplicate(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    from evalforge_api.application import test_case_service

    fixture = await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-a",
        email="a@example.com",
    )
    existing = await add_test_case(
        fixture=fixture, repositories=evaluation_repositories, content={"input": "retired case"}
    )
    await test_case_service.archive_test_case(
        context=fixture.context,
        test_case_id=existing.test_case_id,
        repositories=evaluation_repositories,
    )

    duplicates = await duplicate_detection_service.check_for_duplicates(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        content=TestCaseContent(input="retired case"),
        repositories=evaluation_repositories,
    )
    assert duplicates == ()


async def test_the_latest_version_defines_the_duplicate_fingerprint(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    from evalforge_api.application import test_case_service

    fixture = await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-a",
        email="a@example.com",
    )
    version = await add_test_case(
        fixture=fixture, repositories=evaluation_repositories, content={"input": "original"}
    )
    await test_case_service.create_test_case_version(
        context=fixture.context,
        test_case_id=version.test_case_id,
        content={"input": "revised"},
        repositories=evaluation_repositories,
    )

    against_old = await duplicate_detection_service.check_for_duplicates(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        content=TestCaseContent(input="original"),
        repositories=evaluation_repositories,
    )
    against_new = await duplicate_detection_service.check_for_duplicates(
        context=fixture.context,
        dataset_id=fixture.dataset_id,
        content=TestCaseContent(input="revised"),
        repositories=evaluation_repositories,
    )
    assert against_old == ()
    assert against_new == (version.test_case_id,)


async def test_checking_against_another_tenants_dataset_discloses_nothing(
    evaluation_repositories: EvaluationRepositories,
    create_tenant: CreateTenant,
    create_user: CreateUser,
    build_tenant_context: BuildContext,
) -> None:
    """Tenant A asking about Tenant B's dataset ID gets the same answer
    as asking about a random UUID: nothing."""
    tenant_a = await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-a",
        email="a@example.com",
    )
    tenant_b = await bootstrap_dataset(
        repositories=evaluation_repositories,
        create_tenant=create_tenant,
        create_user=create_user,
        build_tenant_context=build_tenant_context,
        slug="tenant-b",
        email="b@example.com",
    )
    await add_test_case(
        fixture=tenant_b,
        repositories=evaluation_repositories,
        content={"input": "tenant-b secret question"},
    )

    against_tenant_b = await duplicate_detection_service.check_for_duplicates(
        context=tenant_a.context,
        dataset_id=tenant_b.dataset_id,
        content=TestCaseContent(input="tenant-b secret question"),
        repositories=evaluation_repositories,
    )
    against_random = await duplicate_detection_service.check_for_duplicates(
        context=tenant_a.context,
        dataset_id=uuid4(),
        content=TestCaseContent(input="tenant-b secret question"),
        repositories=evaluation_repositories,
    )
    assert against_tenant_b == ()
    assert against_tenant_b == against_random
