from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from evalforge_api.domain.sampling import (
    InvalidSamplingRequestError,
    deterministic_sample,
    deterministic_split,
)

_FIXED_IDS: tuple[UUID, ...] = tuple(
    UUID(f"00000000-0000-4000-8000-{index:012d}") for index in range(40)
)


def test_same_seed_and_inputs_produce_an_identical_sample() -> None:
    first = deterministic_sample(_FIXED_IDS, sample_size=10, seed="seed-a")
    second = deterministic_sample(_FIXED_IDS, sample_size=10, seed="seed-a")
    assert first == second


def test_input_order_does_not_affect_the_sample() -> None:
    forward = deterministic_sample(_FIXED_IDS, sample_size=10, seed="seed-a")
    reversed_order = deterministic_sample(
        tuple(reversed(_FIXED_IDS)), sample_size=10, seed="seed-a"
    )
    assert forward == reversed_order


def test_a_different_seed_produces_a_different_sample() -> None:
    first = deterministic_sample(_FIXED_IDS, sample_size=10, seed="seed-a")
    second = deterministic_sample(_FIXED_IDS, sample_size=10, seed="seed-b")
    assert first != second


def test_the_sample_is_a_subset_with_no_duplicates() -> None:
    sampled = deterministic_sample(_FIXED_IDS, sample_size=13, seed="seed-a")
    assert len(sampled) == 13
    assert len(set(sampled)) == 13
    assert set(sampled) <= set(_FIXED_IDS)


def test_a_sample_is_a_prefix_of_a_larger_sample_under_the_same_seed() -> None:
    """Rank ordering is stable, so growing the sample only appends."""
    small = deterministic_sample(_FIXED_IDS, sample_size=5, seed="seed-a")
    large = deterministic_sample(_FIXED_IDS, sample_size=12, seed="seed-a")
    assert large[:5] == small


def test_sampling_the_whole_population_returns_every_item() -> None:
    sampled = deterministic_sample(_FIXED_IDS, sample_size=len(_FIXED_IDS), seed="seed-a")
    assert set(sampled) == set(_FIXED_IDS)


def test_sampling_more_than_the_population_is_rejected() -> None:
    with pytest.raises(InvalidSamplingRequestError):
        deterministic_sample(_FIXED_IDS, sample_size=len(_FIXED_IDS) + 1, seed="seed-a")


def test_a_negative_sample_size_is_rejected() -> None:
    with pytest.raises(InvalidSamplingRequestError):
        deterministic_sample(_FIXED_IDS, sample_size=-1, seed="seed-a")


def test_an_empty_seed_is_rejected() -> None:
    with pytest.raises(InvalidSamplingRequestError):
        deterministic_sample(_FIXED_IDS, sample_size=1, seed="")


def test_split_assigns_every_item_exactly_once() -> None:
    buckets = deterministic_split(
        _FIXED_IDS, ratios={"train": 0.6, "validation": 0.2, "test": 0.2}, seed="seed-a"
    )
    assigned = [item for members in buckets.values() for item in members]
    assert sorted(assigned, key=str) == sorted(_FIXED_IDS, key=str)
    assert len(assigned) == len(set(assigned)) == len(_FIXED_IDS)


def test_split_always_returns_every_named_bucket() -> None:
    buckets = deterministic_split((), ratios={"train": 0.5, "test": 0.5}, seed="seed-a")
    assert buckets == {"train": (), "test": ()}


def test_same_seed_produces_an_identical_split() -> None:
    ratios = {"train": 0.7, "test": 0.3}
    first = deterministic_split(_FIXED_IDS, ratios=ratios, seed="seed-a")
    second = deterministic_split(_FIXED_IDS, ratios=ratios, seed="seed-a")
    assert first == second


def test_a_different_seed_produces_a_different_split() -> None:
    ratios = {"train": 0.5, "test": 0.5}
    first = deterministic_split(_FIXED_IDS, ratios=ratios, seed="seed-a")
    second = deterministic_split(_FIXED_IDS, ratios=ratios, seed="seed-b")
    assert first != second


def test_split_bucket_order_in_the_mapping_does_not_change_the_result() -> None:
    forward = deterministic_split(_FIXED_IDS, ratios={"a": 0.3, "b": 0.3, "c": 0.4}, seed="seed-a")
    reordered = deterministic_split(
        _FIXED_IDS, ratios={"c": 0.4, "b": 0.3, "a": 0.3}, seed="seed-a"
    )
    assert forward == reordered


def test_ratios_that_do_not_sum_to_one_are_rejected() -> None:
    with pytest.raises(InvalidSamplingRequestError):
        deterministic_split(_FIXED_IDS, ratios={"train": 0.5, "test": 0.2}, seed="seed-a")


def test_a_non_positive_ratio_is_rejected() -> None:
    with pytest.raises(InvalidSamplingRequestError):
        deterministic_split(_FIXED_IDS, ratios={"train": 1.0, "test": 0.0}, seed="seed-a")


def test_no_buckets_at_all_is_rejected() -> None:
    with pytest.raises(InvalidSamplingRequestError):
        deterministic_split(_FIXED_IDS, ratios={}, seed="seed-a")


def test_a_single_bucket_absorbs_the_entire_population() -> None:
    buckets = deterministic_split(_FIXED_IDS, ratios={"all": 1.0}, seed="seed-a")
    assert buckets["all"] == _FIXED_IDS


def test_split_roughly_honours_the_requested_proportions() -> None:
    population = tuple(uuid4() for _ in range(2_000))
    buckets = deterministic_split(
        population, ratios={"train": 0.8, "test": 0.2}, seed="proportion-check"
    )
    assert 0.75 < len(buckets["train"]) / len(population) < 0.85
