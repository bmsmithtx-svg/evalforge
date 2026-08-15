from __future__ import annotations

from uuid import uuid4

import pytest

from evalforge_api.domain.evaluation_enums import DatasetSnapshotStatus
from evalforge_api.domain.versioning import (
    ImmutableRecordError,
    LineageViolationError,
    ensure_snapshot_is_draft,
    next_version_number,
    validate_lineage_within_resource,
    validate_snapshot_item_dataset,
)


def test_next_version_number_starts_at_one_for_an_empty_resource() -> None:
    assert next_version_number([]) == 1


def test_next_version_number_is_one_past_the_highest_existing_version() -> None:
    assert next_version_number([1, 2, 3]) == 4
    assert next_version_number([1, 5, 3]) == 6


def test_lineage_within_the_same_resource_is_valid() -> None:
    resource_id = uuid4()
    validate_lineage_within_resource(
        version_resource_id=resource_id, derived_from_resource_id=resource_id
    )


def test_lineage_with_no_parent_is_valid() -> None:
    validate_lineage_within_resource(version_resource_id=uuid4(), derived_from_resource_id=None)


def test_lineage_across_different_resources_is_rejected() -> None:
    with pytest.raises(LineageViolationError):
        validate_lineage_within_resource(
            version_resource_id=uuid4(), derived_from_resource_id=uuid4()
        )


def test_draft_snapshot_passes_the_draft_check() -> None:
    ensure_snapshot_is_draft(DatasetSnapshotStatus.DRAFT)


def test_finalized_snapshot_fails_the_draft_check() -> None:
    with pytest.raises(ImmutableRecordError):
        ensure_snapshot_is_draft(DatasetSnapshotStatus.FINALIZED)


def test_archived_snapshot_fails_the_draft_check() -> None:
    with pytest.raises(ImmutableRecordError):
        ensure_snapshot_is_draft(DatasetSnapshotStatus.ARCHIVED)


def test_snapshot_item_from_the_same_dataset_is_valid() -> None:
    dataset_id = uuid4()
    validate_snapshot_item_dataset(item_dataset_id=dataset_id, snapshot_dataset_id=dataset_id)


def test_snapshot_item_from_a_different_dataset_is_rejected() -> None:
    with pytest.raises(LineageViolationError):
        validate_snapshot_item_dataset(item_dataset_id=uuid4(), snapshot_dataset_id=uuid4())
