"""Canonical hashing for evaluation-significant content.

Structured content (JSON-shaped version content, snapshot membership)
must hash identically regardless of incidental serialization behavior
such as dictionary key order — see docs/REPRODUCIBILITY_CONTRACT.md.
Raw bytes (artifact payloads) hash directly.

``hash()`` is never used here: it is process-randomized for strings by
default in CPython and unsuitable for durable identity or integrity.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

HASH_ALGORITHM = "sha256"
CANONICALIZATION_VERSION = "json-canonical-v1"


def canonicalize_json(content: Any) -> bytes:
    """Serialize JSON-compatible content into a deterministic byte form.

    Keys are sorted recursively (``sort_keys=True`` applies at every
    nesting level), separators are fixed with no incidental
    whitespace, and non-ASCII characters are escaped so the resulting
    bytes do not depend on the platform's default text encoding.
    Logically identical content — regardless of the original key
    insertion order or formatting — always produces the same bytes.
    """
    return json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_canonical_content(content: Any) -> str:
    """Hash JSON-compatible structured content deterministically."""
    return hash_bytes(canonicalize_json(content))
