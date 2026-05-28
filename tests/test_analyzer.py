"""Tests for depagon.analyzer and renderers."""

from pathlib import Path

import pytest

from depagon.analyzer import Analyzer
from depagon.renderers import render_dot, render_mermaid


def test_unused_import_flagged(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text("import os\n\ndef foo():\n    return 1\n")
    result = Analyzer().analyze(tmp_path)
    unused = [f for f in result.findings if f.kind == "unused_import"]
    assert any("os" in f.detail for f in unused)


def test_used_import_not_flagged(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text(
        "import os\n\ndef foo():\n    return os.getcwd()\n"
    )
    result = Analyzer().analyze(tmp_path)
    unused_os = [
        f for f in result.findings if f.kind == "unused_import" and "os" in f.detail
    ]
    assert unused_os == []


def test_internal_cycle_detected(tmp_path: Path) -> None:
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("from mypkg import b\n")
    (pkg / "b.py").write_text("from mypkg import a\n")
    result = Analyzer().analyze(tmp_path)
    cycles = [f for f in result.findings if f.kind == "cycle"]
    assert len(cycles) >= 1


def test_no_false_positive_external(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text("import os\nimport sys\n\nprint(os.getcwd(), sys.argv)\n")
    result = Analyzer().analyze(tmp_path)
    cycles = [f for f in result.findings if f.kind == "cycle"]
    assert cycles == []


def test_mermaid_output_structure(tmp_path: Path) -> None:
    (tmp_path / "alpha.py").write_text("x = 1\n")
    (tmp_path / "beta.py").write_text("from alpha import x\n")
    result = Analyzer().analyze(tmp_path)
    mermaid = render_mermaid(result)
    assert mermaid.startswith("graph TD")


def test_dot_output_structure(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text("import os\n")
    result = Analyzer().analyze(tmp_path)
    dot = render_dot(result)
    assert "digraph depagon" in dot
    assert "mod" in dot


def test_coupling_in_result(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("from pkg import b\n")
    (pkg / "b.py").write_text("x = 1\n")
    result = Analyzer().analyze(tmp_path)
    assert "pkg.a" in result.coupling
    assert "pkg.b" in result.coupling
    fi_b, fo_b = result.coupling["pkg.b"]
    assert fi_b >= 1
