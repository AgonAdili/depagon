"""Output renderers: rich terminal report, Mermaid, Graphviz DOT, JSON, HTML."""

from __future__ import annotations

import json as _json
from collections import defaultdict
from datetime import datetime

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


def render_json(result: AnalysisResult) -> str:
    """Return a JSON string of the full analysis result."""
    apps = sorted({_app(n) for n in result.graph.nodes() if n})
    cross = _cross_app_summary(result)
    ranked = sorted(result.coupling.items(), key=lambda kv: kv[1][0], reverse=True)
    data = {
        "summary": {
            "modules": len(result.graph.nodes()),
            "apps": len(apps),
            "edges": len(result.graph.edges()),
            "cycles": sum(1 for f in result.findings if f.kind == "cycle"),
            "unused_imports": sum(1 for f in result.findings if f.kind == "unused_import"),
        },
        "nodes": sorted(result.graph.nodes()),
        "edges": [list(e) for e in sorted(result.graph.edges())],
        "coupling": {
            mod: {"fan_in": fi, "fan_out": fo}
            for mod, (fi, fo) in ranked
        },
        "findings": [
            {"kind": f.kind, "detail": f.detail, "location": f.location}
            for f in result.findings
        ],
        "cross_app": {
            src_app: dict(dst_apps)
            for src_app, dst_apps in sorted(cross.items())
        },
    }
    return _json.dumps(data, indent=2)


def render_html(result: AnalysisResult) -> str:
    """Return a self-contained HTML report with an interactive dependency graph."""
    graph = result.graph
    coupling = result.coupling
    findings = result.findings
    apps = sorted({_app(n) for n in graph.nodes() if n})
    cross = _cross_app_summary(result)
    cycles = [f for f in findings if f.kind == "cycle"]
    unused = [f for f in findings if f.kind == "unused_import"]
    ranked = sorted(coupling.items(), key=lambda kv: kv[1][0], reverse=True)

    palette = [
        "#0EA5E9","#10B981","#F59E0B","#EF4444",
        "#8B5CF6","#06B6D4","#EC4899","#84CC16",
        "#F97316","#A855F7","#14B8A6","#EAB308",
    ]
    app_color = {a: palette[i % len(palette)] for i, a in enumerate(apps)}

    # ── Embedded data ─────────────────────────────────────────────────────
    graph_data = {
        "nodes": [
            {
                "id": n, "app": _app(n),
                "color": app_color.get(_app(n), "#64748B"),
                "fan_in": coupling.get(n, (0, 0))[0],
                "fan_out": coupling.get(n, (0, 0))[1],
            }
            for n in sorted(graph.nodes())
        ],
        "edges": [list(e) for e in sorted(graph.edges())],
        "findings": [
            {"kind": f.kind, "detail": f.detail, "location": f.location}
            for f in findings
        ],
    }
    data_json = _json.dumps(graph_data)

    # ── Stats bar ─────────────────────────────────────────────────────────
    cycle_color = "#EF4444" if cycles else "#10B981"
    stats_html = "".join(
        f'<div class="stat"><div class="stat-val" style="color:{c}">{v}</div>'
        f'<div class="stat-lbl">{l}</div></div>'
        for v, l, c in [
            (len(graph.nodes()), "Modules",       "#0EA5E9"),
            (len(apps),          "Apps",           "#8B5CF6"),
            (len(graph.edges()), "Edges",          "#06B6D4"),
            (len(cycles),        "Cycles",         cycle_color),
            (len(unused),        "Unused Imports", "#F59E0B"),
        ]
    )

    # ── App filter options ────────────────────────────────────────────────
    app_opts = "".join(f'<option value="{a}">{a}</option>' for a in apps)

    # ── Legend ────────────────────────────────────────────────────────────
    legend_html = "".join(
        f'<span class="legend-item" onclick="filterApp(\'{a}\')">'
        f'<span class="ldot" style="background:{app_color[a]}"></span>{a}</span>'
        for a in apps
    )

    # ── Findings ─────────────────────────────────────────────────────────
    def _finding_card(kind: str, detail: str, location: str) -> str:
        if kind == "cycle":
            col, label = "#EF4444", "cycle"
        else:
            col, label = "#F59E0B", "unused import"
        loc_line = f'<div class="finding-loc">{location}</div>' if location else ""
        return (
            f'<div class="finding-card" style="border-left-color:{col}">'
            f'<span class="finding-badge" style="background:{col}22;color:{col}">{label}</span>'
            f'<div><div class="finding-detail">{detail}</div>{loc_line}</div>'
            f"</div>"
        )

    if findings:
        cards = "".join(_finding_card(f.kind, f.detail, f.location) for f in findings)
        findings_section = (
            '<div class="section">'
            f'<div class="section-head"><h2>Findings <span class="badge">{len(findings)}</span></h2></div>'
            f'<div class="findings-list">{cards}</div>'
            "</div>"
        )
    else:
        findings_section = (
            '<div class="section">'
            '<div class="section-head"><h2>Findings</h2></div>'
            '<div class="empty">No findings — clean project.</div>'
            "</div>"
        )

    # ── Coupling table ────────────────────────────────────────────────────
    _extra = ' class="coup-extra hidden"'
    coupling_rows = "".join(
        f'<tr{("" if i < 10 else _extra)}>'
        f'<td class="mono">{mod}</td>'
        f'<td class="num" data-val="{fi}" style="color:#10B981">{fi}</td>'
        f'<td class="num" data-val="{fo}">{fo}</td>'
        f"</tr>"
        for i, (mod, (fi, fo)) in enumerate(ranked)
    )
    remaining = max(0, len(ranked) - 10)
    show_more_btn = (
        f'<div class="show-more-wrap">'
        f'<button class="btn show-more-btn" onclick="toggleCoupling(this)">'
        f'Show {remaining} more module{"s" if remaining != 1 else ""}'
        f"</button></div>"
        if remaining > 0 else ""
    )
    coupling_section = (
        '<div class="section">'
        '<div class="section-head">'
        '<h2>Coupling Report</h2>'
        f'<span class="badge">{len(ranked)} modules</span>'
        "</div>"
        '<div class="table-wrap"><table>'
        '<thead><tr>'
        '<th onclick="sortTbl(0)">Module</th>'
        '<th onclick="sortTbl(1)">Fan-in ↕</th>'
        '<th onclick="sortTbl(2)">Fan-out ↕</th>'
        "</tr></thead>"
        f'<tbody id="coup-tbody">{coupling_rows}</tbody>'
        f"</table></div>{show_more_btn}</div>"
    )

    # ── Cross-app section ─────────────────────────────────────────────────
    if cross:
        cross_rows = "".join(
            "<tr><td>" + src +
            "</td><td>" +
            "  &nbsp; ".join(
                f'<span style="color:{app_color.get(dst,"#64748B")}">{dst}</span>'
                f' <span class="dim">({n})</span>'
                for dst, n in sorted(deps.items(), key=lambda kv: -kv[1])
            ) + "</td></tr>"
            for src, deps in sorted(cross.items())
        )
        cross_section = (
            '<div class="section">'
            '<div class="section-head"><h2>Cross-App Dependencies</h2></div>'
            '<div class="table-wrap"><table>'
            "<thead><tr><th>App</th><th>Imports from</th></tr></thead>"
            f"<tbody>{cross_rows}</tbody>"
            "</table></div></div>"
        )
    else:
        cross_section = ""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    return _HTML_TEMPLATE \
        .replace("%%TITLE%%",     f"depagon report · {timestamp}") \
        .replace("%%TIMESTAMP%%", timestamp) \
        .replace("%%STATS%%",     stats_html) \
        .replace("%%APP_OPTS%%",  app_opts) \
        .replace("%%LEGEND%%",    legend_html) \
        .replace("%%FINDINGS%%",  findings_section) \
        .replace("%%COUPLING%%",  coupling_section) \
        .replace("%%CROSS%%",     cross_section) \
        .replace("%%DATA_JSON%%", data_json)


# ── HTML template (CSS + JS embedded) ────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%%TITLE%%</title>
<style>
:root{--bg:#060B18;--surf:#0D1B2A;--card:#122033;--text:#F0F8FF;--muted:#64748B;
  --border:#1A2F4A;--blue:#0EA5E9;--green:#10B981;--orange:#F59E0B;--red:#EF4444;
  --rad:8px;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:14px;line-height:1.5;}
a{color:var(--blue);}
header{background:var(--surf);border-bottom:1px solid var(--border);
  padding:12px 24px;display:flex;align-items:center;justify-content:space-between;
  position:sticky;top:0;z-index:100;}
.logo{font-size:22px;font-weight:800;color:var(--blue);letter-spacing:-0.5px;}
.hright{font-size:12px;color:var(--muted);text-align:right;}
.stats-bar{display:flex;background:var(--surf);border-bottom:1px solid var(--border);
  overflow-x:auto;}
.stat{flex:1;min-width:110px;padding:14px 18px;text-align:center;
  border-right:1px solid var(--border);}
.stat:last-child{border-right:none;}
.stat:hover{background:var(--card);}
.stat-val{font-size:26px;font-weight:800;line-height:1;margin-bottom:3px;}
.stat-lbl{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;}
.container{max-width:1400px;margin:0 auto;padding:20px;display:flex;
  flex-direction:column;gap:20px;}
.section{background:var(--surf);border:1px solid var(--border);border-radius:var(--rad);
  overflow:hidden;}
.section-head{padding:14px 18px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;}
.section-head h2{font-size:15px;font-weight:700;}
.badge{background:#1A2F4A;color:var(--muted);font-size:11px;font-weight:600;
  padding:2px 8px;border-radius:10px;}
.controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center;}
.controls select,.controls input{background:var(--card);border:1px solid var(--border);
  color:var(--text);padding:5px 10px;border-radius:6px;font-size:13px;outline:none;}
.controls select:focus,.controls input:focus{border-color:var(--blue);}
.btn{background:var(--card);border:1px solid var(--border);color:var(--text);
  padding:5px 12px;border-radius:6px;font-size:13px;cursor:pointer;}
.btn:hover{border-color:var(--blue);color:var(--blue);}
.graph-wrap{position:relative;background:#020810;height:520px;overflow:hidden;}
#svg{width:100%;height:100%;cursor:grab;display:block;}
#svg:active{cursor:grabbing;}
.tooltip{position:absolute;background:#1A2F4A;border:1px solid var(--border);
  border-radius:8px;padding:10px 14px;font-size:12px;pointer-events:none;
  max-width:260px;box-shadow:0 4px 20px rgba(0,0,0,.6);z-index:10;display:none;}
.tt-title{font-weight:700;margin-bottom:6px;word-break:break-all;}
.tt-row{color:var(--muted);margin-top:2px;}
.tt-row b{color:var(--text);}
.legend{padding:10px 18px;border-top:1px solid var(--border);
  display:flex;flex-wrap:wrap;gap:10px;font-size:12px;}
.legend-item{display:flex;align-items:center;gap:6px;cursor:pointer;
  padding:3px 8px;border-radius:4px;}
.legend-item:hover{background:var(--card);}
.ldot{width:10px;height:10px;border-radius:50%;flex-shrink:0;}
.findings-list{padding:14px 18px;display:flex;flex-direction:column;gap:8px;}
.finding-card{display:flex;align-items:flex-start;gap:12px;padding:10px 14px;
  background:var(--card);border-radius:6px;border-left:3px solid transparent;}
.finding-badge{font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;
  white-space:nowrap;flex-shrink:0;margin-top:1px;}
.finding-detail{font-size:13px;color:var(--text);}
.finding-loc{font-size:11px;color:var(--muted);font-family:monospace;margin-top:2px;}
.table-wrap{overflow-x:auto;}
table{width:100%;border-collapse:collapse;font-size:13px;}
thead th{background:#080F1C;padding:9px 16px;text-align:left;font-weight:600;
  font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;
  cursor:pointer;user-select:none;white-space:nowrap;}
thead th:hover{color:var(--text);}
tbody tr{border-top:1px solid #0F2040;}
tbody tr:hover{background:var(--card);}
td{padding:8px 16px;}
.mono{font-family:'Courier New',monospace;font-size:12px;}
.num{text-align:right;font-weight:600;}
.dim{color:var(--muted);}
.empty{padding:28px;text-align:center;color:var(--muted);font-style:italic;}
.coup-extra.hidden{display:none;}
.show-more-wrap{padding:12px 18px;border-top:1px solid var(--border);text-align:center;}
.show-more-btn{padding:7px 20px;font-size:13px;color:var(--blue);border-color:var(--blue);}
.show-more-btn:hover{background:#0EA5E911;}
</style>
</head>
<body>
<header>
  <div>
    <span class="logo">depagon</span>
    <span style="color:var(--muted);margin-left:10px;font-size:13px">
      Dependency Analysis Report
    </span>
  </div>
  <div class="hright">Generated %%TIMESTAMP%%</div>
</header>

<div class="stats-bar">%%STATS%%</div>

<div class="container">

  <!-- Graph -->
  <div class="section">
    <div class="section-head">
      <h2>Dependency Graph</h2>
      <div class="controls">
        <select id="app-filter">
          <option value="">All Apps</option>%%APP_OPTS%%
        </select>
        <input id="search" type="text" placeholder="Search module..." style="width:180px">
        <button class="btn" onclick="resetLayout()">Reset</button>
      </div>
    </div>
    <div class="graph-wrap">
      <svg id="svg"></svg>
      <div class="tooltip" id="tooltip"></div>
    </div>
    <div class="legend">%%LEGEND%%</div>
  </div>

  %%FINDINGS%%
  %%COUPLING%%
  %%CROSS%%

  <div style="text-align:center;padding:12px;color:var(--muted);font-size:12px">
    Generated by <strong style="color:var(--blue)">depagon</strong>
  </div>
</div>

<script>
const DATA = %%DATA_JSON%%;

// ── Assign colours ───────────────────────────────────────────────────────────
const PALETTE=['#0EA5E9','#10B981','#F59E0B','#EF4444','#8B5CF6',
               '#06B6D4','#EC4899','#84CC16','#F97316','#A855F7'];
const apps=[...new Set(DATA.nodes.map(n=>n.app))].sort();
const appColor=Object.fromEntries(apps.map((a,i)=>[a,PALETTE[i%PALETTE.length]]));
DATA.nodes.forEach(n=>{ if(!n.color) n.color=appColor[n.app]||'#64748B'; });

// ── Force simulation ─────────────────────────────────────────────────────────
const svgEl=document.getElementById('svg');
const W=svgEl.clientWidth||900, H=svgEl.clientHeight||520;

const nodeById={};
const simNodes=DATA.nodes.map(n=>{
  const o={...n,x:W/2+(Math.random()-.5)*280,y:H/2+(Math.random()-.5)*280,
            vx:0,vy:0,fixed:false,fx:0,fy:0};
  nodeById[n.id]=o; return o;
});
const simLinks=DATA.edges
  .map(([s,t])=>({source:nodeById[s],target:nodeById[t]}))
  .filter(l=>l.source&&l.target);

function simTick(){
  const REP=2600,SL=95,SK=0.065,GR=0.018,D=0.87;
  for(let i=0;i<simNodes.length;i++){
    for(let j=i+1;j<simNodes.length;j++){
      const a=simNodes[i],b=simNodes[j];
      const dx=(b.x-a.x)||.01,dy=(b.y-a.y)||.01;
      const d2=dx*dx+dy*dy,d=Math.sqrt(d2)||1;
      const f=REP/d2,fx=f*dx/d,fy=f*dy/d;
      if(!a.fixed){a.vx-=fx;a.vy-=fy;}
      if(!b.fixed){b.vx+=fx;b.vy+=fy;}
    }
  }
  for(const l of simLinks){
    const a=l.source,b=l.target;
    const dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)||1;
    const f=(d-SL)*SK,fx=f*dx/d,fy=f*dy/d;
    if(!a.fixed){a.vx+=fx;a.vy+=fy;}
    if(!b.fixed){b.vx-=fx;b.vy-=fy;}
  }
  for(const n of simNodes){
    if(n.fixed){n.x=n.fx;n.y=n.fy;continue;}
    n.vx+=(W/2-n.x)*GR; n.vy+=(H/2-n.y)*GR;
    n.vx*=D; n.vy*=D;
    n.x=Math.max(55,Math.min(W-55,n.x+n.vx));
    n.y=Math.max(28,Math.min(H-28,n.y+n.vy));
  }
}

// Initial layout — run offline before first paint
for(let i=0;i<220;i++) simTick();

// ── SVG elements ─────────────────────────────────────────────────────────────
const NS='http://www.w3.org/2000/svg';
const mk=(tag,attrs)=>{
  const e=document.createElementNS(NS,tag);
  Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));
  return e;
};

const defs=mk('defs',{});
svgEl.appendChild(defs);

// Single arrow marker
const marker=mk('marker',{id:'arr',markerWidth:'8',markerHeight:'6',
  refX:'6',refY:'3',orient:'auto'});
marker.appendChild(mk('path',{d:'M0,0 L8,3 L0,6 Z',fill:'#475569'}));
defs.appendChild(marker);

const linkG=mk('g',{});
svgEl.appendChild(linkG);
const nodeG=mk('g',{});
svgEl.appendChild(nodeG);

const tip=document.getElementById('tooltip');
let sel=null;

const linkEls=simLinks.map(l=>{
  const line=mk('line',{stroke:l.source.color,'stroke-width':'1.3',
    'stroke-opacity':'.5','marker-end':'url(#arr)'});
  linkG.appendChild(line);
  return{el:line,l};
});

const nodeEls=simNodes.map(n=>{
  const g=mk('g',{cursor:'pointer'});
  const ring=mk('circle',{r:'14',fill:'none',stroke:n.color,
    'stroke-width':'2',opacity:'0'});
  // Size node by fan_in (slightly bigger for high fan-in)
  const r=Math.min(10+n.fan_in*0.8,18);
  const circ=mk('circle',{r,fill:n.color,'fill-opacity':'.82'});
  const lbl=mk('text',{dy:'3px','text-anchor':'middle',fill:'#F0F8FF',
    'font-size':'6','pointer-events':'none','font-family':'monospace'});
  const parts=n.id.split('.');
  lbl.textContent=parts[parts.length-1];
  g.append(ring,circ,lbl);
  nodeG.appendChild(g);

  // Hover
  g.addEventListener('mouseenter',e=>{
    ring.setAttribute('opacity','.55');
    const inCycle=DATA.findings.some(f=>f.kind==='cycle'&&f.detail.includes(n.id));
    tip.innerHTML=`<div class="tt-title">${n.id}</div>
      <div class="tt-row">App: <b>${n.app}</b></div>
      <div class="tt-row">Fan-in: <b>${n.fan_in}</b> &nbsp; Fan-out: <b>${n.fan_out}</b></div>
      ${inCycle?'<div class="tt-row" style="color:#EF4444;margin-top:4px">&#9888; Involved in a cycle</div>':''}`;
    tip.style.display='block';
    moveTip(e);
  });
  g.addEventListener('mousemove',moveTip);
  g.addEventListener('mouseleave',()=>{
    if(sel!==n) ring.setAttribute('opacity','0');
    tip.style.display='none';
  });
  g.addEventListener('click',e=>{
    e.stopPropagation();
    if(sel===n){sel=null;unhighlight();}
    else{sel=n;highlight(n.id);}
  });

  // Drag
  let drag=false;
  g.addEventListener('mousedown',e=>{drag=true;n.fixed=true;e.preventDefault();});
  window.addEventListener('mousemove',e=>{
    if(!drag)return;
    const r=svgEl.getBoundingClientRect();
    n.fx=e.clientX-r.left; n.fy=e.clientY-r.top;
    n.x=n.fx; n.y=n.fy; draw();
  });
  window.addEventListener('mouseup',()=>{if(drag){drag=false;n.fixed=false;}});

  return{g,ring,circ,n};
});

function moveTip(e){
  const r=svgEl.getBoundingClientRect();
  tip.style.left=Math.min(e.clientX-r.left+14,W-270)+'px';
  tip.style.top=Math.max(0,e.clientY-r.top-10)+'px';
}

function highlight(id){
  const conn=new Set([id]);
  simLinks.forEach(l=>{
    if(l.source.id===id)conn.add(l.target.id);
    if(l.target.id===id)conn.add(l.source.id);
  });
  nodeEls.forEach(({g,ring,n})=>{
    g.setAttribute('opacity',conn.has(n.id)?'1':'.1');
    ring.setAttribute('opacity',n.id===id?'.55':'0');
  });
  linkEls.forEach(({el,l})=>{
    const on=l.source.id===id||l.target.id===id;
    el.setAttribute('opacity',on?'.9':'.04');
    el.setAttribute('stroke-width',on?'2':'1');
  });
}

function unhighlight(){
  nodeEls.forEach(({g,ring})=>{g.setAttribute('opacity','1');ring.setAttribute('opacity','0');});
  linkEls.forEach(({el})=>{el.setAttribute('opacity','.5');el.setAttribute('stroke-width','1.3');});
}

svgEl.addEventListener('click',()=>{sel=null;unhighlight();});

// ── Draw ─────────────────────────────────────────────────────────────────────
function draw(){
  linkEls.forEach(({el,l})=>{
    const s=l.source,t=l.target;
    const dx=t.x-s.x,dy=t.y-s.y,d=Math.sqrt(dx*dx+dy*dy)||1;
    const ex=t.x-dx/d*15,ey=t.y-dy/d*15;
    el.setAttribute('x1',s.x);el.setAttribute('y1',s.y);
    el.setAttribute('x2',ex);el.setAttribute('y2',ey);
  });
  nodeEls.forEach(({g,n})=>g.setAttribute('transform',`translate(${n.x},${n.y})`));
}

let ticks=0;
(function loop(){
  if(ticks<280){simTick();ticks++;}
  draw();
  requestAnimationFrame(loop);
})();

// ── Controls ──────────────────────────────────────────────────────────────────
function filterApp(v){
  v=v||document.getElementById('app-filter').value;
  if(!v){unhighlight();return;}
  nodeEls.forEach(({g,n})=>g.setAttribute('opacity',n.app===v?'1':'.07'));
  linkEls.forEach(({el,l})=>{
    const on=l.source.app===v&&l.target.app===v;
    el.setAttribute('opacity',on?'.85':'.03');
  });
}
document.getElementById('app-filter').onchange=e=>filterApp(e.target.value);

document.getElementById('search').oninput=function(){
  const q=this.value.toLowerCase().trim();
  if(!q){unhighlight();return;}
  const hits=simNodes.filter(n=>n.id.toLowerCase().includes(q));
  if(hits.length===1){sel=hits[0];highlight(hits[0].id);}
  else nodeEls.forEach(({g,n})=>
    g.setAttribute('opacity',n.id.toLowerCase().includes(q)?'1':'.1'));
};

function resetLayout(){
  simNodes.forEach(n=>{
    n.x=W/2+(Math.random()-.5)*280; n.y=H/2+(Math.random()-.5)*280;
    n.vx=0;n.vy=0;n.fixed=false;
  });
  ticks=0; sel=null; unhighlight();
  document.getElementById('app-filter').value='';
  document.getElementById('search').value='';
}

// ── Show more / collapse coupling table ──────────────────────────────────────
function toggleCoupling(btn){
  const rows=document.querySelectorAll('.coup-extra');
  const expanding=rows[0]&&rows[0].classList.contains('hidden');
  rows.forEach(r=>r.classList.toggle('hidden'));
  btn.textContent=expanding
    ?'Show less'
    :`Show ${rows.length} more module${rows.length!==1?'s':''}`;
}

// ── Sortable coupling table ───────────────────────────────────────────────────
let sCol=1,sDir=-1;
function sortTbl(col){
  if(sCol===col)sDir*=-1; else{sCol=col;sDir=-1;}
  const tb=document.getElementById('coup-tbody');
  const rows=[...tb.querySelectorAll('tr')];
  rows.sort((a,b)=>{
    const av=a.cells[col].dataset.val||a.cells[col].textContent;
    const bv=b.cells[col].dataset.val||b.cells[col].textContent;
    const an=parseFloat(av),bn=parseFloat(bv);
    return isNaN(an)||isNaN(bn)?av.localeCompare(bv)*sDir:(an-bn)*sDir;
  });
  rows.forEach(r=>tb.appendChild(r));
}
</script>
</body>
</html>"""
