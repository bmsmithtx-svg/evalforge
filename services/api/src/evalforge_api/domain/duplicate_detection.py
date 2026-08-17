"""Deterministic, structural duplicate detection for test cases.

Scope: exact-duplicate detection only. Semantic or embedding-based
similarity is explicitly out of scope for Milestone 6 — the rule here
is fully deterministic, explainable, and reproducible offline, which a
similarity model would not be.

The rule
--------
1. Normalize the test case's ``input``:
   - a string is whitespace-collapsed (every run of whitespace becomes
     a single space), stripped, and case-folded, so ``"  Hello   World "``
     and ``"hello world"`` normalize identically;
   - a JSON object is left structurally intact and canonicalized with
     ``evalforge_api.domain.hashing.canonicalize_json``, so key order
     and incidental formatting do not matter.
2. Hash the normalized form with the same SHA-256 canonical-JSON
   scheme used for every other content hash in the platform
   (docs/REPRODUCIBILITY_CONTRACT.md) — no second hashing scheme is
   introduced.

Two test-case versions are exact duplicates *within one dataset* iff
their ``dedup_hash`` values match. Only ``input`` participates: two
cases with the same input but different expected outputs are a
conflicting pair a reviewer must resolve, and surfacing them is the
point of the check.
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from evalforge_api.domain.hashing import canonicalize_json, hash_bytes
from evalforge_api.domain.test_case_content import TestCaseContent

DEDUP_RULE_VERSION = "dedup-input-v1"


def normalize_text_input(value: str) -> str:
    """Collapse whitespace, strip, and case-fold a free-text input."""
    return " ".join(value.split()).strip().casefold()


def compute_dedup_hash(content: TestCaseContent) -> str:
    """The dataset-scoped duplicate-detection fingerprint of a test case."""
    if isinstance(content.input, str):
        normalized: object = {"kind": "text", "value": normalize_text_input(content.input)}
    else:
        normalized = {"kind": "structured", "value": content.input}
    return hash_bytes(canonicalize_json({"rule": DEDUP_RULE_VERSION, "input": normalized}))


def find_duplicate_ids(candidate_hash: str, existing: Mapping[UUID, str]) -> tuple[UUID, ...]:
    """Every existing test-case ID whose current content is an exact
    duplicate of ``candidate_hash``, in a deterministic order.

    ``existing`` is always a tenant- and dataset-scoped mapping built
    by the caller; this function never reaches outside it, so it cannot
    disclose another tenant's data.
    """
    matches = [
        test_case_id
        for test_case_id, existing_hash in existing.items()
        if existing_hash == candidate_hash
    ]
    return tuple(sorted(matches, key=str))
