"""Deterministic, reproducible sampling and splitting of dataset items.

``random`` is deliberately not used anywhere in this module: a sampled
or split evaluation set must be reconstructable from the seed and the
item IDs alone, on any machine, in any process, at any time
(docs/REPRODUCIBILITY_CONTRACT.md). Python's ``random`` module would
tie the result to an interpreter's PRNG implementation and to call
ordering.

Algorithm
---------
Every item is assigned a *rank* derived only from the seed and its own
stable ID::

    rank(item)  = sha256(f"{seed}:{item_id}")            # hex digest
    unit(item)  = int(rank, 16) / 2**256                 # a value in [0, 1)

``deterministic_sample`` sorts items by ``(rank, str(item_id))``
ascending and returns the first ``sample_size`` of them, in that rank
order. The ``str(item_id)`` tiebreaker makes the order total even in
the (cryptographically implausible) case of a rank collision.

``deterministic_split`` assigns each item to exactly one named bucket
by walking the bucket names in a fixed, explicit order — ascending
alphabetical order of the bucket name, never the caller's mapping
insertion order — accumulating their ratios into half-open boundaries
``[0, r1)``, ``[r1, r1+r2)``, ... and selecting the bucket whose
interval contains ``unit(item)``. The final bucket absorbs the
remainder, so floating-point accumulation can never leave an item
unassigned. Items keep their input order within a bucket.

Consequences, both relied on by the tests: the same seed and the same
items always produce the same output, and every item lands in exactly
one bucket.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from evalforge_api.domain.hashing import hash_bytes

_HASH_SPACE = 2**256
_RATIO_TOLERANCE = 1e-9


class InvalidSamplingRequestError(Exception):
    """Raised when a sample size or a set of split ratios is unusable."""


def item_rank(item_id: UUID, *, seed: str) -> str:
    """The stable hex rank of one item under one seed."""
    return hash_bytes(f"{seed}:{item_id}".encode())


def _unit_interval_value(item_id: UUID, *, seed: str) -> float:
    return int(item_rank(item_id, seed=seed), 16) / _HASH_SPACE


def deterministic_sample(
    item_ids: Sequence[UUID], *, sample_size: int, seed: str
) -> tuple[UUID, ...]:
    """The stable top-``sample_size`` items by hash rank."""
    if sample_size < 0:
        raise InvalidSamplingRequestError("sample_size must not be negative.")
    if not seed:
        raise InvalidSamplingRequestError("A sampling seed is required.")
    if sample_size > len(item_ids):
        raise InvalidSamplingRequestError(
            f"sample_size {sample_size} exceeds the available {len(item_ids)} item(s)."
        )
    ranked = sorted(item_ids, key=lambda item_id: (item_rank(item_id, seed=seed), str(item_id)))
    return tuple(ranked[:sample_size])


def deterministic_split(
    item_ids: Sequence[UUID], *, ratios: Mapping[str, float], seed: str
) -> dict[str, tuple[UUID, ...]]:
    """Partition items into named buckets; every item lands in exactly one."""
    if not seed:
        raise InvalidSamplingRequestError("A sampling seed is required.")
    if not ratios:
        raise InvalidSamplingRequestError("At least one split bucket is required.")
    for name, ratio in ratios.items():
        if not name.strip():
            raise InvalidSamplingRequestError("Split bucket names must not be blank.")
        if ratio <= 0:
            raise InvalidSamplingRequestError(f"Split ratio for {name!r} must be greater than 0.")
    total = sum(ratios.values())
    if abs(total - 1.0) > _RATIO_TOLERANCE:
        raise InvalidSamplingRequestError(f"Split ratios must sum to 1.0 (received {total}).")

    ordered_names = sorted(ratios)
    boundaries: list[tuple[str, float]] = []
    cumulative = 0.0
    for name in ordered_names:
        cumulative += ratios[name]
        boundaries.append((name, cumulative))

    buckets: dict[str, list[UUID]] = {name: [] for name in ordered_names}
    for item_id in item_ids:
        value = _unit_interval_value(item_id, seed=seed)
        # The last bucket absorbs the remainder, so accumulated
        # floating-point error can never leave an item unassigned.
        chosen = ordered_names[-1]
        for name, upper in boundaries:
            if value < upper:
                chosen = name
                break
        buckets[chosen].append(item_id)
    return {name: tuple(members) for name, members in buckets.items()}
