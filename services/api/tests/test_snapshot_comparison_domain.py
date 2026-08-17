from __future__ import annotations

from uuid import UUID, uuid4

from evalforge_api.domain.snapshot_comparison import (
    SnapshotMembershipEntry,
    compare_snapshot_membership,
)


def _entry(
    test_case_id: UUID, *, version_number: int, content_hash: str
) -> SnapshotMembershipEntry:
    return SnapshotMembershipEntry(
        test_case_id=test_case_id,
        test_case_version_id=uuid4(),
        version_number=version_number,
        content_hash=content_hash,
    )


def test_added_removed_changed_and_unchanged_are_all_reported() -> None:
    kept = uuid4()
    revised = uuid4()
    dropped = uuid4()
    introduced = uuid4()

    left = [
        _entry(kept, version_number=1, content_hash="hash-kept"),
        _entry(revised, version_number=1, content_hash="hash-old"),
        _entry(dropped, version_number=3, content_hash="hash-dropped"),
    ]
    right = [
        _entry(kept, version_number=1, content_hash="hash-kept"),
        _entry(revised, version_number=2, content_hash="hash-new"),
        _entry(introduced, version_number=1, content_hash="hash-new-case"),
    ]

    result = compare_snapshot_membership(left, right)
    assert result.added == (introduced,)
    assert result.removed == (dropped,)
    assert result.changed == ((revised, 1, 2),)
    assert result.unchanged == (kept,)


def test_a_case_with_the_same_hash_at_a_different_version_number_is_unchanged() -> None:
    """Identity is the frozen content hash, not the version number."""
    case_id = uuid4()
    left = [_entry(case_id, version_number=1, content_hash="same")]
    right = [_entry(case_id, version_number=7, content_hash="same")]
    result = compare_snapshot_membership(left, right)
    assert result.unchanged == (case_id,)
    assert result.changed == ()


def test_two_empty_snapshots_compare_as_entirely_empty() -> None:
    result = compare_snapshot_membership([], [])
    assert result.added == ()
    assert result.removed == ()
    assert result.changed == ()
    assert result.unchanged == ()


def test_results_are_sorted_by_test_case_id_string_form() -> None:
    ids = [
        UUID("cccccccc-0000-0000-0000-000000000000"),
        UUID("aaaaaaaa-0000-0000-0000-000000000000"),
        UUID("bbbbbbbb-0000-0000-0000-000000000000"),
    ]
    right = [_entry(case_id, version_number=1, content_hash="h") for case_id in ids]
    result = compare_snapshot_membership([], right)
    assert result.added == tuple(sorted(ids, key=str))


def test_comparison_is_deterministic_across_repeated_calls_and_input_order() -> None:
    kept = uuid4()
    revised = uuid4()
    dropped = uuid4()
    introduced = uuid4()
    left = [
        _entry(dropped, version_number=1, content_hash="d"),
        _entry(kept, version_number=1, content_hash="k"),
        _entry(revised, version_number=1, content_hash="old"),
    ]
    right = [
        _entry(introduced, version_number=1, content_hash="i"),
        _entry(revised, version_number=4, content_hash="new"),
        _entry(kept, version_number=1, content_hash="k"),
    ]

    first = compare_snapshot_membership(left, right)
    second = compare_snapshot_membership(left, right)
    reordered = compare_snapshot_membership(list(reversed(left)), list(reversed(right)))

    assert first == second
    assert first == reordered


def test_comparison_is_directional() -> None:
    only_left = uuid4()
    left = [_entry(only_left, version_number=1, content_hash="h")]
    forward = compare_snapshot_membership(left, [])
    backward = compare_snapshot_membership([], left)
    assert forward.removed == (only_left,)
    assert backward.added == (only_left,)
