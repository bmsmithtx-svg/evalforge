#!/usr/bin/env python3
"""Validate relative Markdown links across README.md and docs/**/*.md.

Checks that every non-HTTP relative link target resolves to an existing
file (and, for in-page anchors, an existing heading). Reports every
broken link rather than stopping at the first one.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LINK_PATTERN = re.compile(r"\]\(([^)]+)\)")
HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.*)$")


def slugify_heading(heading: str) -> str:
    text = heading.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text


def headings_in(path: Path) -> set[str]:
    slugs = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING_PATTERN.match(line)
        if match:
            slugs.add(slugify_heading(match.group(1)))
    return slugs


def markdown_files(repo_root: Path) -> list[Path]:
    files = [repo_root / "README.md"]
    docs_dir = repo_root / "docs"
    if docs_dir.is_dir():
        files.extend(sorted(docs_dir.rglob("*.md")))
    return [path for path in files if path.is_file()]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    broken: list[str] = []

    for md_file in markdown_files(repo_root):
        content = md_file.read_text(encoding="utf-8")
        for link in LINK_PATTERN.findall(content):
            if link.startswith(("http://", "https://", "mailto:")):
                continue

            target_part, _, anchor = link.partition("#")

            if not target_part:
                # In-page anchor like [text](#heading).
                if anchor and anchor not in headings_in(md_file):
                    broken.append(f"{md_file.relative_to(repo_root)} -> {link} (anchor not found)")
                continue

            target_path = (md_file.parent / target_part).resolve()
            if not target_path.is_file():
                broken.append(f"{md_file.relative_to(repo_root)} -> {link} (file not found)")
                continue

            if anchor and target_path.suffix == ".md" and anchor not in headings_in(target_path):
                broken.append(f"{md_file.relative_to(repo_root)} -> {link} (anchor not found)")

    if broken:
        print(f"Markdown link check FAILED: {len(broken)} broken link(s).")
        for item in broken:
            print(f"  {item}")
        return 1

    print("Markdown link check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
