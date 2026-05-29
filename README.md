# depagon

**depagon** is a Python CLI tool and library that analyzes the import dependency structure of a Python project. It parses every `.py` file using the standard-library `ast` module, builds a directed graph of internal module dependencies, and reports:

- **Circular imports** — cycles in the dependency graph.
- **Unused imports** — names imported but never referenced in the same file.
- **Coupling metrics** — fan-in (how many modules import a given module) and fan-out (how many modules it imports).

It works as both a command-line tool (`depagon scan ...`) and an importable library.

---

## Install

```bash
pip install depagon
```

Requires Python 3.9 or later. The only runtime dependency is [`rich`](https://github.com/Textualize/rich).

---

## Usage

### Tree output (default)

Renders a dependency tree, coupling table, and findings in the terminal:

```bash
depagon scan path/to/myproject
```

### Mermaid diagram

```bash
depagon scan path/to/myproject --output mermaid
```

Outputs a `graph TD` Mermaid string that can be pasted into any Mermaid-compatible renderer (GitHub Markdown, Mermaid Live Editor, etc.).

### Graphviz DOT

```bash
depagon scan path/to/myproject --output dot
```

Outputs a DOT string suitable for `dot -Tpng -o graph.png`.

### JSON export

```bash
depagon scan path/to/myproject --output json
depagon scan path/to/myproject --output json > report.json
```

Returns a machine-readable JSON object containing `summary`, `nodes`, `edges`, `coupling` (fan-in + fan-out per module), `findings`, and `cross_app`. Pipe it into `jq` or any downstream tool.

### HTML report

```bash
depagon scan path/to/myproject --output html > report.html
open report.html
```

Generates a fully self-contained HTML file (no external dependencies) with:

- **Interactive dependency graph** — force-directed layout, draggable nodes sized by fan-in, coloured by app
- **Hover tooltips** — fan-in, fan-out, and cycle warnings per module
- **Click to highlight** — shows a node's direct connections
- **Filter by app** — dropdown to isolate one top-level package
- **Search** — highlight matching modules instantly
- **Coupling report** — sortable table, shows first 10 rows with a **Show more** button for the rest
- **Findings** — cycles and unused imports as colour-coded cards
- **Cross-app dependencies** — grouped by source app

### Show unused imports

```bash
depagon scan path/to/myproject --unused
```

Unused-import findings are collected during every run but only displayed when `--unused` is passed.

### CI integration — exit code on cycles

```bash
depagon scan path/to/myproject --detect-cycles
```

Exits with status `1` if any circular imports are found, `0` otherwise. Wire it into your CI pipeline:

```yaml
# GitHub Actions example
- run: depagon scan src/ --detect-cycles
```

---

## Library usage

```python
from depagon import Analyzer
from depagon.renderers import render_mermaid

result = Analyzer().analyze(Path("src/"))

# Inspect findings
for finding in result.findings:
    print(finding.kind, finding.location, finding.detail)

# Render
print(render_mermaid(result))
```

Public API:

| Symbol | Module |
|---|---|
| `Scanner`, `ImportInfo`, `ModuleFile` | `depagon.scanner` |
| `DependencyGraph` | `depagon.graph` |
| `Analyzer`, `AnalysisResult`, `Finding` | `depagon.analyzer` |
| `render_tree`, `render_mermaid`, `render_dot`, `render_json`, `render_html` | `depagon.renderers` |

All of the above are also re-exported from `depagon` directly.

---

## Skipped directories

The scanner automatically skips the following directory names to avoid scanning virtual environments and build artifacts:

```
__pycache__  venv  .venv  env  .env  envs  virtualenv  .virtualenv
node_modules  .tox  .mypy_cache  dist  build  .pytest_cache  .eggs  site-packages
migrations
```

Any directory whose name starts with `.` (hidden directories) is also skipped.

If your environment uses a different name (e.g. `my_env`, `.project_venv`, `py310`), you can exclude it by subclassing `Scanner` and overriding `_SKIP_DIRS`:

```python
from depagon.scanner import Scanner, _SKIP_DIRS

class MyScanner(Scanner):
    pass

# Add your custom env name to the skip set
import depagon.scanner as _s
_s._SKIP_DIRS = _SKIP_DIRS | {"my_env", "py310", ".project_venv"}
```

Or build the graph programmatically and pass a custom scanner to the analyzer:

```python
from pathlib import Path
import depagon.scanner as scanner_mod
from depagon.scanner import Scanner, _SKIP_DIRS
from depagon.analyzer import Analyzer

# Extend the skip set before scanning
scanner_mod._SKIP_DIRS = _SKIP_DIRS | {"my_env"}

result = Analyzer().analyze(Path("src/"))
```

---

## How it works

1. **Scanning** — `Scanner.scan(root)` walks the directory tree (skipping the directories listed above), reads each `.py` file, and parses it with `ast.parse`. Files with syntax errors are skipped with a warning. Every `import` and `from ... import` statement is recorded as an `ImportInfo`.

2. **Graph construction** — `Analyzer.analyze(root)` resolves each import to its absolute dotted module name, checks whether it refers to a file inside the scanned directory (internal module), and adds a directed edge to a `DependencyGraph`.

3. **Cycle detection** — `DependencyGraph.find_cycles()` uses a colored DFS (white / gray / black) with a recursion stack. When a gray (in-progress) node is encountered again, the slice of the current path forms a cycle. Duplicate cycles are deduplicated via a frozenset key.

4. **Unused-import detection** — For each file, `ast.walk` collects every `ast.Name` identifier. Any bound import name absent from this set is flagged. This is a conservative heuristic: `import os` is considered used if `os` appears anywhere as an identifier in the file.

5. **Rendering** — Five renderers produce different output formats from the same `AnalysisResult`: rich terminal tree, Mermaid diagram, Graphviz DOT, JSON, and an interactive HTML report.

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```
