#!/usr/bin/env python3
"""Scan tracked files for common committed-secret patterns.

Lightweight, dependency-free complement to a dedicated secret scanner.
Scans only ``git ls-files`` output so untracked local artifacts (.env,
caches, build output) are never included.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS access key ID", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "Assigned secret-like literal",
        re.compile(
            r"(?i)(password|secret|api[_-]?key|token)\s*[:=]\s*['\"][A-Za-z0-9/+_\-]{12,}['\"]"
        ),
    ),
)

EXCLUDED_SUFFIXES = {".lock", ".png", ".jpg", ".jpeg", ".ico", ".woff", ".woff2"}
EXCLUDED_PATH_MARKERS = (".env.example", "package-lock.json")


def tracked_files(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [repo_root / line for line in result.stdout.splitlines() if line]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    findings: list[str] = []

    for path in tracked_files(repo_root):
        if path.suffix in EXCLUDED_SUFFIXES:
            continue
        if any(marker in path.name for marker in EXCLUDED_PATH_MARKERS):
            continue
        if not path.is_file():
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for label, pattern in PATTERNS:
            for match in pattern.finditer(text):
                line_number = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path.relative_to(repo_root)}:{line_number}: {label}")

    if findings:
        print(f"Secret scan FAILED: {len(findings)} potential secret(s) found.")
        for item in findings:
            print(f"  {item}")
        return 1

    print("Secret scan passed: no committed-secret patterns found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
