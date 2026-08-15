#!/usr/bin/env python3
"""Enforce allowed-dependency-direction rules for the evalforge_api package.

See docs/ARCHITECTURE.md's "Allowed Dependency Direction" and
"Independence Requirement" sections. Ports must stay independent of
delivery and provider-specific code so they remain a stable interface
that adapters implement, not the other way around.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

API_PACKAGE_ROOT = Path("services/api/src/evalforge_api")

# (module-prefix-relative-to-package, forbidden-imported-prefixes)
RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ports", ("evalforge_api.adapters", "evalforge_api.routes", "evalforge_api.app", "fastapi", "starlette")),
)


def imported_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
    return names


def module_name_for(path: Path, package_root: Path) -> str:
    relative = path.relative_to(package_root.parent).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    package_root = repo_root / API_PACKAGE_ROOT
    if not package_root.is_dir():
        print("Dependency-boundary check skipped: evalforge_api package not present yet.")
        return 0

    violations: list[str] = []

    for py_file in sorted(package_root.rglob("*.py")):
        module_name = module_name_for(py_file, package_root)
        relative_module = module_name.removeprefix("evalforge_api.")

        for prefix, forbidden in RULES:
            if not relative_module.startswith(prefix):
                continue
            for imported in imported_names(py_file):
                if any(imported == f or imported.startswith(f + ".") for f in forbidden):
                    violations.append(
                        f"{py_file.relative_to(repo_root)}: '{relative_module}' imports forbidden "
                        f"'{imported}'"
                    )

    if violations:
        print(f"Dependency-boundary check FAILED: {len(violations)} violation(s).")
        for item in violations:
            print(f"  {item}")
        return 1

    print("Dependency-boundary check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
