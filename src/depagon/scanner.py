"""Walk a Python project directory and extract import information via AST parsing."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

_SKIP_DIRS: frozenset[str] = frozenset(
    {
        "__pycache__",
        "venv",
        ".venv",
        "node_modules",
        ".tox",
        ".mypy_cache",
        "dist",
        "build",
        ".pytest_cache",
        ".eggs",
    }
)


@dataclass
class ImportInfo:
    """A single import statement extracted from a source file.

    `names` holds the identifiers bound in the local namespace — e.g. for
    ``import os as o`` it is ``["o"]``; for ``from os import path, getcwd``
    it is ``["path", "getcwd"]``.  This is the correct input for unused-import
    detection without any further alias resolution.
    """

    module: str
    names: list[str]
    lineno: int
    is_relative: bool
    level: int = 0


@dataclass
class ModuleFile:
    """Represents one parsed ``.py`` file inside the scanned project."""

    path: Path
    module_name: str  # dotted name relative to the project root
    imports: list[ImportInfo]
    source: str


class Scanner:
    """Walks a directory tree and produces a :class:`ModuleFile` per ``.py`` file."""

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def scan(self, root: Path) -> list[ModuleFile]:
        """Return one :class:`ModuleFile` for every parseable ``.py`` file under *root*."""
        root = root.resolve()
        results: list[ModuleFile] = []
        for path in self._iter_python_files(root):
            module_file = self._parse_file(path, root)
            if module_file is not None:
                results.append(module_file)
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_python_files(self, root: Path):
        for path in sorted(root.rglob("*.py")):
            rel_parts = path.relative_to(root).parts
            # Skip if any directory component is hidden or in the skip-set.
            if any(
                p.startswith(".") or p in _SKIP_DIRS for p in rel_parts[:-1]
            ):
                continue
            yield path

    def _parse_file(self, path: Path, root: Path) -> ModuleFile | None:
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            self.warnings.append(f"Skipping {path}: {exc}")
            return None
        module_name = self._path_to_module(path, root)
        imports = self._extract_imports(tree)
        return ModuleFile(
            path=path,
            module_name=module_name,
            imports=imports,
            source=source,
        )

    def _path_to_module(self, path: Path, root: Path) -> str:
        """Convert a filesystem path to a dotted module name."""
        rel = path.relative_to(root)
        parts = list(rel.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][:-3]  # strip .py
        return ".".join(parts)

    def _extract_imports(self, tree: ast.Module) -> list[ImportInfo]:
        """Walk *tree* and return an :class:`ImportInfo` for every import node."""
        imports: list[ImportInfo] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bound = alias.asname or alias.name.split(".")[0]
                    imports.append(
                        ImportInfo(
                            module=alias.name,
                            names=[bound],
                            lineno=node.lineno,
                            is_relative=False,
                            level=0,
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                is_rel = node.level > 0
                names = [
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name != "*"
                ]
                imports.append(
                    ImportInfo(
                        module=mod,
                        names=names,
                        lineno=node.lineno,
                        is_relative=is_rel,
                        level=node.level,
                    )
                )
        return imports
