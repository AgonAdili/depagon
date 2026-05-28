"""Directed dependency graph with cycle detection and coupling metrics."""

from __future__ import annotations


class DependencyGraph:
    """Directed graph whose nodes are dotted module names.

    Backed by an adjacency map ``{src: {dst, ...}}``.  All mutating methods
    are idempotent — adding the same node or edge twice is safe.
    """

    def __init__(self) -> None:
        self._adj: dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_node(self, name: str) -> None:
        """Ensure *name* exists in the graph (no-op if already present)."""
        if name not in self._adj:
            self._adj[name] = set()

    def add_edge(self, src: str, dst: str) -> None:
        """Add a directed edge from *src* to *dst*, creating nodes as needed."""
        self.add_node(src)
        self.add_node(dst)
        self._adj[src].add(dst)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def nodes(self) -> list[str]:
        """Return all node names in insertion order."""
        return list(self._adj.keys())

    def edges(self) -> list[tuple[str, str]]:
        """Return all edges as ``(src, dst)`` pairs."""
        return [
            (src, dst)
            for src, dsts in self._adj.items()
            for dst in sorted(dsts)
        ]

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def fan_out(self, node: str) -> int:
        """Number of modules that *node* directly imports."""
        return len(self._adj.get(node, set()))

    def fan_in(self, node: str) -> int:
        """Number of modules that directly import *node*."""
        return sum(1 for dsts in self._adj.values() if node in dsts)

    def coupling_report(self) -> dict[str, tuple[int, int]]:
        """Return ``{module: (fan_in, fan_out)}`` for every node."""
        return {node: (self.fan_in(node), self.fan_out(node)) for node in self._adj}

    # ------------------------------------------------------------------
    # Cycle detection
    # ------------------------------------------------------------------

    def find_cycles(self) -> list[list[str]]:
        """Return all simple cycles found via colored DFS.

        Each returned list is the cycle path ending with the repeated start
        node, e.g. ``["a", "b", "a"]``.  Duplicate cycles (same node-set,
        different starting point) are deduplicated.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {n: WHITE for n in self._adj}
        path: list[str] = []
        cycles: list[list[str]] = []
        seen: set[frozenset[str]] = set()

        def dfs(node: str) -> None:
            color[node] = GRAY
            path.append(node)
            for neighbor in sorted(self._adj.get(node, set())):
                if color[neighbor] == GRAY:
                    idx = path.index(neighbor)
                    cycle_nodes = path[idx:]
                    key = frozenset(cycle_nodes)
                    if key not in seen:
                        seen.add(key)
                        cycles.append(cycle_nodes + [neighbor])
                elif color[neighbor] == WHITE:
                    dfs(neighbor)
            path.pop()
            color[node] = BLACK

        for node in sorted(self._adj.keys()):
            if color[node] == WHITE:
                dfs(node)

        return cycles
