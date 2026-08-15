"""Version-numbering, immutability, and lineage policy.

Pure domain rules with no persistence dependency. The PostgreSQL layer
enforces the same invariants independently (composite tenant-scoped
foreign keys, immutability triggers, and privilege grants) — this
module is the first line of defense and the place these rules are
unit-tested without a database.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from evalforge_api.domain.evaluation_enums import DatasetSnapshotStatus


class ImmutableRecordError(Exception):
    """Raised when code attempts to mutate a finalized, immutable record."""


class LineageViolationError(Exception):
    """Raised when a lineage reference would cross resources or tenants."""


def next_version_number(existing_version_numbers: Iterable[int]) -> int:
    """The next sequential version number for a logical resource.

    Versions are never renumbered or reused: a resource with versions
    {1, 2, 3} always produces 4 next, even if higher numbers were later
    archived (archival never deletes the row).
    """
    highest = max(existing_version_numbers, default=0)
    return highest + 1


def validate_lineage_within_resource(
    *, version_resource_id: UUID, derived_from_resource_id: UUID | None
) -> None:
    """A version may only derive from a prior version of the *same*
    logical resource. Deriving across resources or kinds would let one
    resource's history silently absorb another's, which breaks the
    "logical resource" identity guarantee the domain model requires.
    """
    if derived_from_resource_id is None:
        return
    if derived_from_resource_id != version_resource_id:
        raise LineageViolationError(
            "A version may only derive from a prior version of the same logical resource."
        )


def ensure_snapshot_is_draft(status: DatasetSnapshotStatus) -> None:
    """Membership may only be added while a snapshot is still a draft.

    Once finalized, membership, hash, and lineage are frozen —
    supported application paths must never add, remove, or substitute
    a test-case version afterward.
    """
    if status != DatasetSnapshotStatus.DRAFT:
        raise ImmutableRecordError(
            f"Dataset snapshot is '{status.value}' and can no longer accept membership changes."
        )


def validate_snapshot_item_dataset(*, item_dataset_id: UUID, snapshot_dataset_id: UUID) -> None:
    """A snapshot may only freeze test-case versions belonging to its
    own dataset — never a version borrowed from an unrelated dataset.
    """
    if item_dataset_id != snapshot_dataset_id:
        raise LineageViolationError(
            "A snapshot may only include test-case versions from its own dataset."
        )
