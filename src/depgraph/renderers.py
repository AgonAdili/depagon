"""Output renderers: rich terminal tree, Mermaid diagram, and Graphviz DOT."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from depgraph.analyzer import AnalysisResult

_console = Console()


def render_tree(result: AnalysisResult) -> None:
    """Print a rich dependency tree, coupling table, and findings table."""
    graph = result.graph

    tree = Tree("[bold]Dependency Graph[/bold]")
    for node in sorted(graph.nodes()):
        branch = tree.add(f"[cyan]{node}[/cyan]")
        for dst in sorted(graph._adj.get(node, set())):
            branch.add(f"[dim]{dst}[/dim]")

    _console.print(tree)
    _console.print()

    coupling_table = Table(title="Coupling Report", show_header=True, header_style="bold")
    coupling_table.add_column("Module", no_wrap=True)
    coupling_table.add_column("Fan-in", justify="right")
    coupling_table.add_column("Fan-out", justify="right")
    for node in sorted(result.coupling.keys()):
        fi, fo = result.coupling[node]
        coupling_table.add_row(node, str(fi), str(fo))
    _console.print(coupling_table)

    if result.findings:
        _console.print()
        findings_table = Table(title="Findings", show_header=True, header_style="bold")
        findings_table.add_column("Kind", no_wrap=True)
        findings_table.add_column("Location", no_wrap=True)
        findings_table.add_column("Detail")
        for finding in result.findings:
            color = "red" if finding.kind == "cycle" else "yellow"
            findings_table.add_row(
                f"[{color}]{finding.kind}[/{color}]",
                finding.location,
                finding.detail,
            )
        _console.print(findings_table)


def render_mermaid(result: AnalysisResult) -> str:
    """Return a Mermaid ``graph TD`` string for the dependency graph."""
    lines = ["graph TD"]
    edges = result.graph.edges()
    if not edges:
        lines.append("    %% no edges")
    else:
        for src, dst in sorted(edges):
            src_id = src.replace(".", "_")
            dst_id = dst.replace(".", "_")
            lines.append(f'    {src_id}["{src}"] --> {dst_id}["{dst}"]')
    return "\n".join(lines)


def render_dot(result: AnalysisResult) -> str:
    """Return a Graphviz DOT string for the dependency graph."""
    lines = ["digraph depgraph {", "    rankdir=LR;"]
    for node in sorted(result.graph.nodes()):
        lines.append(f'    "{node}";')
    for src, dst in sorted(result.graph.edges()):
        lines.append(f'    "{src}" -> "{dst}";')
    lines.append("}")
    return "\n".join(lines)
