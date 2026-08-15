#!/usr/bin/env python3
"""Enforce the 300-physical-line file-size ceiling.

See docs/MODULARITY_STANDARD.md. Reports every violation with its path
and physical line count rather than stopping at the first failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

MAX_PHYSICAL_LINES = 300
CHECKED_EXTENSIONS = (".py", ".ts", ".tsx", ".js")
CHECKED_ROOTS = ("apps", "packages", "services", "scripts", "tests")

EXCLUDED_DIR_NAMES = {
    "node_modules",
    ".next",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "coverage",
    ".git",
}


def iter_checked_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for root_name in CHECKED_ROOTS:
        root = repo_root / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in CHECKED_EXTENSIONS:
                continue
            if any(part in EXCLUDED_DIR_NAMES for part in path.relative_to(repo_root).parts):
                continue
            files.append(path)
    return sorted(files)


def count_physical_lines(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    violations: list[tuple[Path, int]] = []

    for path in iter_checked_files(repo_root):
        line_count = count_physical_lines(path)
        if line_count > MAX_PHYSICAL_LINES:
            violations.append((path.relative_to(repo_root), line_count))

    if violations:
        print(f"Modularity check FAILED: {len(violations)} file(s) exceed {MAX_PHYSICAL_LINES} lines.")
        for path, line_count in violations:
            print(f"  {path}: {line_count} lines")
        return 1

    print("Modularity check passed: no file exceeds the 300-line ceiling.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
