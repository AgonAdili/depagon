"""Output renderers: rich terminal report, Mermaid diagram, and Graphviz DOT."""

from __future__ import annotations

from collections import defaultdict

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from depagon.analyzer import AnalysisResult

_console = Console()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _app(module_name: str) -> str:
    """Return the top-level package name for a dotted module name."""
    return module_name.split(".")[0] if module_name else ""


def _cross_app_summary(result: AnalysisResult) -> dict[str, dict[str, int]]:
    """Return {src_app: {dst_app: edge_count}} for every cross-app edge."""
    cross: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for src, dst in result.graph.edges():
        sa, da = _app(src), _app(dst)
        if sa and da and sa != da:
            cross[sa][da] += 1
    return dict(cross)


# ------------------------------------------------------------------
# Renderers
# ------------------------------------------------------------------

def render_tree(result: AnalysisResult) -> None:
    """Print a structured analysis report to the terminal."""
    graph = result.graph
    coupling = result.coupling
    cycles = [f for f in result.findings if f.kind == "cycle"]
    unused = [f for f in result.findings if f.kind == "unused_import"]

    apps = sorted({_app(n) for n in graph.nodes() if n})

    # ── Summary panel ────────────────────────────────────────────────────
    cycle_color = "red" if cycles else "green"
    summary = (
        f"  [bold]Modules[/bold]  {len(graph.nodes())}"
        f"    [bold]Apps[/bold]  {len(apps)}"
        f"    [bold]Edges[/bold]  {len(graph.edges())}"
        f"    [bold]Cycles[/bold]  [{cycle_color}]{len(cycles)}[/{cycle_color}]"
        f"    [bold]Unused imports[/bold]  {len(unused)}"
    )
    _console.print(Panel(summary, title="[bold]Project Summary[/bold]", expand=False))
    _console.print()

    # ── Most depended-on modules ─────────────────────────────────────────
    ranked = sorted(coupling.items(), key=lambda kv: kv[1][0], reverse=True)
    top = [(mod, fi, fo) for mod, (fi, fo) in ranked if fi > 0][:8]
    if top:
        _console.print(Rule("[bold]Most Depended-On Modules[/bold]"))
        t = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0, 1))
        t.add_column("#", style="dim", width=3)
        t.add_column("Module", style="cyan", no_wrap=True)
        t.add_column("Fan-in", justify="right", style="bold green")
        t.add_column("Fan-out", justify="right")
        for i, (mod, fi, fo) in enumerate(top, 1):
            t.add_row(str(i), mod, str(fi), str(fo))
        _console.print(t)
        _console.print()

    # ── Cycles ──────────────────────────────────────────────────────────
    cycle_header = (
        f"[bold]Cycles — [red]{len(cycles)} found[/red][/bold]"
        if cycles
        else "[bold]Cycles[/bold]"
    )
    _console.print(Rule(cycle_header))
    if cycles:
        for i, f in enumerate(cycles, 1):
            _console.print(f"  [bold red]{i}.[/bold red]  {f.detail}")
    else:
        _console.print("  [green]No circular imports detected.[/green]")
    _console.print()

    # ── Cross-app dependencies ───────────────────────────────────────────
    cross = _cross_app_summary(result)
    if cross:
        _console.print(Rule("[bold]Cross-App Dependencies[/bold]"))
        t = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0, 1))
        t.add_column("App", style="cyan", no_wrap=True)
        t.add_column("Imports from")
        for src_app in sorted(cross):
            targets = sorted(cross[src_app].items(), key=lambda kv: -kv[1])
            deps_str = "   ".join(
                f"[bold]{dst}[/bold] [dim]({n} edge{'s' if n != 1 else ''})[/dim]"
                for dst, n in targets
            )
            t.add_row(src_app, deps_str)
        _console.print(t)
        _console.print()

    # ── What's clean ─────────────────────────────────────────────────────
    cycle_apps: set[str] = set()
    for f in cycles:
        for mod in f.detail.split(" -> "):
            cycle_apps.add(_app(mod.strip()))

    clean_apps = [a for a in apps if a not in cycle_apps]
    self_contained = [a for a in apps if a not in cross]

    clean_lines: list[str] = []
    if clean_apps:
        clean_lines.append(f"No cycles in: [green]{', '.join(clean_apps)}[/green]")
    if self_contained:
        clean_lines.append(
            f"No outgoing cross-app imports: [green]{', '.join(self_contained)}[/green]"
        )

    if clean_lines:
        _console.print(Rule("[bold]What's Clean[/bold]"))
        for line in clean_lines:
            _console.print(f"  {line}")
        _console.print()

    # ── Full coupling report ─────────────────────────────────────────────
    _console.print(Rule("[bold]Full Coupling Report[/bold]"))
    t = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0, 1))
    t.add_column("Module", style="cyan", no_wrap=True)
    t.add_column("Fan-in", justify="right", style="green")
    t.add_column("Fan-out", justify="right")
    for mod, (fi, fo) in ranked[:10]:
        t.add_row(mod, str(fi), str(fo))
    _console.print(t)
    if len(ranked) > 10:
        _console.print(
            f"  [dim]... and {len(ranked) - 10} more module(s) not shown.[/dim]"
        )

    # ── Unused imports ───────────────────────────────────────────────────
    if unused:
        _console.print()
        _console.print(Rule("[bold]Unused Imports[/bold]"))
        t = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0, 1))
        t.add_column("Location", style="dim", no_wrap=True)
        t.add_column("Detail")
        for f in unused:
            t.add_row(f.location, f.detail)
        _console.print(t)


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
    lines = ["digraph depagon {", "    rankdir=LR;"]
    for node in sorted(result.graph.nodes()):
        lines.append(f'    "{node}";')
    for src, dst in sorted(result.graph.edges()):
        lines.append(f'    "{src}" -> "{dst}";')
    lines.append("}")
    return "\n".join(lines)
