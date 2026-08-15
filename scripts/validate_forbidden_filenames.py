#!/usr/bin/env python3
"""Reject generic dumping-ground module names.

See docs/MODULARITY_STANDARD.md's "Prohibited Dumping-Ground Modules"
section for the authoritative list.
"""

from __future__ import annotations

import sys
from pathlib import Path

FORBIDDEN_BASENAMES = {
    "utils.py",
    "helpers.py",
    "common.py",
    "utils.ts",
    "helpers.ts",
    "common.ts",
}

CHECKED_ROOTS = ("apps", "packages", "services", "scripts", "tests")
EXCLUDED_DIR_NAMES = {"node_modules", ".next", ".venv", "__pycache__", ".git"}


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    violations: list[Path] = []

    for root_name in CHECKED_ROOTS:
        root = repo_root / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in EXCLUDED_DIR_NAMES for part in path.relative_to(repo_root).parts):
                continue
            if path.name.lower() in FORBIDDEN_BASENAMES:
                violations.append(path.relative_to(repo_root))

    if violations:
        print(f"Forbidden-filename check FAILED: {len(violations)} dumping-ground module(s) found.")
        for path in sorted(violations):
            print(f"  {path}")
        return 1

    print("Forbidden-filename check passed: no dumping-ground modules found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
