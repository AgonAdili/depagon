"""Orchestrates scanning, graph construction, and findings detection."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from depgraph.graph import DependencyGraph
from depgraph.scanner import ImportInfo, ModuleFile, Scanner


@dataclass
class Finding:
    """A single diagnostic produced by the analysis.

    *kind* is either ``"cycle"`` or ``"unused_import"``.
    """

    kind: str
    detail: str
    location: str


@dataclass
class AnalysisResult:
    """Everything produced by :meth:`Analyzer.analyze`."""

    graph: DependencyGraph
    findings: list[Finding]
    coupling: dict[str, tuple[int, int]]
    module_files: list[ModuleFile]


class Analyzer:
    """Runs the scanner, builds the dependency graph, and produces findings."""

    def analyze(self, root: Path) -> AnalysisResult:
        """Scan *root* and return a fully populated :class:`AnalysisResult`."""
        scanner = Scanner()
        module_files = scanner.scan(root)

        internal_modules: set[str] = {mf.module_name for mf in module_files}

        graph = DependencyGraph()
        for mf in module_files:
            graph.add_node(mf.module_name)

        for mf in module_files:
            self._build_edges(mf, internal_modules, graph)

        findings: list[Finding] = []

        for cycle in graph.find_cycles():
            findings.append(
                Finding(
                    kind="cycle",
                    detail=" -> ".join(cycle),
                    location="",
                )
            )

        for mf in module_files:
            findings.extend(self._find_unused(mf))

        coupling = graph.coupling_report()
        return AnalysisResult(
            graph=graph,
            findings=findings,
            coupling=coupling,
            module_files=module_files,
        )

    # ------------------------------------------------------------------
    # Edge building
    # ------------------------------------------------------------------

    def _build_edges(
        self,
        mf: ModuleFile,
        internal_modules: set[str],
        graph: DependencyGraph,
    ) -> None:
        for imp in mf.imports:
            abs_module = self._resolve_absolute(imp, mf.module_name)

            # Direct import of a known internal module.
            if abs_module and abs_module in internal_modules:
                graph.add_edge(mf.module_name, abs_module)

            # Check whether any imported *name* is itself a submodule
            # (handles ``from pkg import submod`` and ``from . import submod``).
            for name in imp.names:
                if not name or name == "*":
                    continue
                candidate = f"{abs_module}.{name}" if abs_module else name
                if candidate in internal_modules:
                    graph.add_edge(mf.module_name, candidate)

    def _resolve_absolute(self, imp: ImportInfo, current_module: str) -> str:
        """Return the absolute dotted module name for *imp*."""
        if not imp.is_relative:
            return imp.module
        pkg = self._get_package(current_module, imp.level)
        if imp.module:
            return f"{pkg}.{imp.module}" if pkg else imp.module
        return pkg

    def _get_package(self, module_name: str, level: int) -> str:
        """Return the ancestor package at *level* dots above *module_name*."""
        parts = module_name.split(".")
        # level=1 means "current package" → remove the last component (the module).
        remaining = parts[:-level] if level <= len(parts) else []
        return ".".join(remaining)

    # ------------------------------------------------------------------
    # Unused-import detection
    # ------------------------------------------------------------------

    def _find_unused(self, mf: ModuleFile) -> list[Finding]:
        """Flag imported names that never appear as identifiers in the file."""
        try:
            tree = ast.parse(mf.source)
        except SyntaxError:
            return []

        used_names: set[str] = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        }

        findings: list[Finding] = []
        for imp in mf.imports:
            # __future__ imports are compiler directives, never identifier uses.
            if imp.module == "__future__":
                continue
            for name in imp.names:
                if not name or name == "*":
                    continue
                if name not in used_names:
                    mod_label = imp.module or "(relative)"
                    findings.append(
                        Finding(
                            kind="unused_import",
                            detail=f"'{name}' imported from '{mod_label}' but never used",
                            location=f"{mf.module_name}:{imp.lineno}",
                        )
                    )
        return findings
