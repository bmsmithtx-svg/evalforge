"""Pure comparison of two frozen dataset-snapshot membership sets.

Given the membership of two finalized snapshots — the same
``(test_case_id, test_case_version_id, version_number, content_hash)``
tuples ``snapshot_service.finalize_snapshot`` hashes — this module
reports what a reader needs to explain a difference in results between
two runs: which logical test cases were added, removed, revised, or
left untouched.

Determinism: every output tuple is sorted by the string form of the
test-case ID, so the same inputs always produce an equal result object
regardless of the order rows came back from the database.

A test case present in both snapshots is ``changed`` iff its frozen
``content_hash`` differs; the version numbers are reported alongside so
the caller can name the exact revision without a second lookup.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SnapshotMembershipEntry:
    test_case_id: UUID
    test_case_version_id: UUID
    version_number: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class SnapshotComparisonResult:
    added: tuple[UUID, ...]
    removed: tuple[UUID, ...]
    changed: tuple[tuple[UUID, int, int], ...]
    unchanged: tuple[UUID, ...]


def compare_snapshot_membership(
    left: Sequence[SnapshotMembershipEntry], right: Sequence[SnapshotMembershipEntry]
) -> SnapshotComparisonResult:
    """Compare ``left`` (the older/base snapshot) against ``right``.

    ``added`` is present in ``right`` only, ``removed`` in ``left``
    only. ``changed`` entries are ``(test_case_id, left_version_number,
    right_version_number)``.
    """
    left_by_case = {entry.test_case_id: entry for entry in left}
    right_by_case = {entry.test_case_id: entry for entry in right}

    added = tuple(sorted((key for key in right_by_case if key not in left_by_case), key=str))
    removed = tuple(sorted((key for key in left_by_case if key not in right_by_case), key=str))

    changed: list[tuple[UUID, int, int]] = []
    unchanged: list[UUID] = []
    for test_case_id in left_by_case.keys() & right_by_case.keys():
        left_entry = left_by_case[test_case_id]
        right_entry = right_by_case[test_case_id]
        if left_entry.content_hash == right_entry.content_hash:
            unchanged.append(test_case_id)
        else:
            changed.append((test_case_id, left_entry.version_number, right_entry.version_number))

    return SnapshotComparisonResult(
        added=added,
        removed=removed,
        changed=tuple(sorted(changed, key=lambda item: str(item[0]))),
        unchanged=tuple(sorted(unchanged, key=str)),
    )
