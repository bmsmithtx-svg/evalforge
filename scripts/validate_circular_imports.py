#!/usr/bin/env python3
"""Detect circular imports within the evalforge_api package.

Builds a directed import graph from AST (both absolute
``evalforge_api.x`` imports and relative imports) and reports any
cycle found, rather than relying on Python's runtime import machinery
to surface it indirectly.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

API_PACKAGE_ROOT = Path("services/api/src/evalforge_api")


def module_name_for(path: Path, package_root: Path) -> str:
    relative = path.relative_to(package_root.parent).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def resolve_relative_import(current_module: str, node: ast.ImportFrom) -> str | None:
    if node.module is None:
        return None
    parts = current_module.split(".")
    package_parts = parts[: -node.level] if node.level else parts
    return ".".join([*package_parts, node.module])


def build_import_graph(package_root: Path) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    all_files = sorted(package_root.rglob("*.py"))
    module_names = {module_name_for(p, package_root) for p in all_files}

    for py_file in all_files:
        module_name = module_name_for(py_file, package_root)
        graph.setdefault(module_name, set())
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))

        for node in ast.walk(tree):
            imported: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in module_names or alias.name.startswith("evalforge_api"):
                        graph[module_name].add(alias.name)
                continue
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    imported = resolve_relative_import(module_name, node)
                elif node.module and node.module.startswith("evalforge_api"):
                    imported = node.module
            if imported and imported in module_names:
                graph[module_name].add(imported)

    return graph


def find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        visiting.add(node)
        path.append(node)
        for neighbor in sorted(graph.get(node, ())):
            if neighbor in visiting:
                return [*path[path.index(neighbor) :], neighbor]
            if neighbor not in visited:
                result = visit(neighbor)
                if result:
                    return result
        visiting.discard(node)
        visited.add(node)
        path.pop()
        return None

    for start_node in sorted(graph):
        if start_node not in visited:
            cycle = visit(start_node)
            if cycle:
                return cycle
    return None


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    package_root = repo_root / API_PACKAGE_ROOT
    if not package_root.is_dir():
        print("Circular-import check skipped: evalforge_api package not present yet.")
        return 0

    graph = build_import_graph(package_root)
    cycle = find_cycle(graph)

    if cycle:
        print("Circular-import check FAILED:")
        print("  " + " -> ".join(cycle))
        return 1

    print("Circular-import check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
