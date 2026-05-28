"""Tests for depgraph.scanner."""

from pathlib import Path

import pytest

from depgraph.scanner import Scanner


def test_extracts_imports(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text(
        "import os\nfrom pathlib import Path\n"
    )
    scanner = Scanner()
    files = scanner.scan(tmp_path)
    assert len(files) == 1
    modules = [imp.module for imp in files[0].imports]
    assert "os" in modules
    assert "pathlib" in modules


def test_skips_syntax_error(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("def (:\n    pass\n")
    scanner = Scanner()
    files = scanner.scan(tmp_path)
    assert files == []
    assert len(scanner.warnings) == 1
    assert "bad.py" in scanner.warnings[0]


def test_module_names(tmp_path: Path) -> None:
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("import os\n")
    scanner = Scanner()
    files = scanner.scan(tmp_path)
    names = {f.module_name for f in files}
    assert "mypkg" in names
    assert "mypkg.mod" in names


def test_bound_names_alias(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text("import os.path as osp\nfrom sys import argv as args\n")
    scanner = Scanner()
    files = scanner.scan(tmp_path)
    all_names = [n for imp in files[0].imports for n in imp.names]
    assert "osp" in all_names
    assert "args" in all_names


def test_skips_venv(tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    venv.mkdir()
    (venv / "site.py").write_text("import os\n")
    (tmp_path / "real.py").write_text("import sys\n")
    scanner = Scanner()
    files = scanner.scan(tmp_path)
    module_names = {f.module_name for f in files}
    assert "real" in module_names
    assert not any("venv" in n for n in module_names)
