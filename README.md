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

Requires Python 3.10 or later. The only runtime dependency is [`rich`](https://github.com/Textualize/rich).

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
| `render_tree`, `render_mermaid`, `render_dot` | `depagon.renderers` |

All of the above are also re-exported from `depagon` directly.

---

## How it works

1. **Scanning** — `Scanner.scan(root)` walks the directory tree (skipping `venv`, `__pycache__`, `.git`, and similar), reads each `.py` file, and parses it with `ast.parse`. Files with syntax errors are skipped with a warning. Every `import` and `from ... import` statement is recorded as an `ImportInfo`.

2. **Graph construction** — `Analyzer.analyze(root)` resolves each import to its absolute dotted module name, checks whether it refers to a file inside the scanned directory (internal module), and adds a directed edge to a `DependencyGraph`.

3. **Cycle detection** — `DependencyGraph.find_cycles()` uses a colored DFS (white / gray / black) with a recursion stack. When a gray (in-progress) node is encountered again, the slice of the current path forms a cycle. Duplicate cycles are deduplicated via a frozenset key.

4. **Unused-import detection** — For each file, `ast.walk` collects every `ast.Name` identifier. Any bound import name absent from this set is flagged. This is a conservative heuristic: `import os` is considered used if `os` appears anywhere as an identifier in the file.

5. **Rendering** — Three renderers produce different output formats from the same `AnalysisResult`.

---

## Building and publishing

Build a distribution:

```bash
pip install build
python -m build
```

This creates `dist/depagon-0.1.0-py3-none-any.whl` and a source tarball.

Upload to PyPI (requires a PyPI account and `twine`):

```bash
pip install twine
twine upload dist/*
```

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```
