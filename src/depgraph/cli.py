"""Command-line entry point for depgraph."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from depgraph.analyzer import Analyzer
from depgraph.renderers import render_dot, render_mermaid, render_tree


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="depgraph",
        description="Analyze the import dependency structure of a Python project.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Scan a Python project directory.")
    scan.add_argument("path", type=Path, help="Path to the project root to analyze.")
    scan.add_argument(
        "--output",
        choices=["tree", "mermaid", "dot"],
        default="tree",
        help="Output format (default: tree).",
    )
    scan.add_argument(
        "--detect-cycles",
        action="store_true",
        help="Exit with status 1 if circular imports are found (useful in CI).",
    )
    scan.add_argument(
        "--unused",
        action="store_true",
        help="Include unused-import findings in the output.",
    )
    return parser


def main() -> None:
    """Entry point wired to the ``depgraph`` console-script."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "scan":
        root = args.path.resolve()
        if not root.is_dir():
            print(f"Error: '{root}' is not a directory.", file=sys.stderr)
            sys.exit(1)

        result = Analyzer().analyze(root)

        if not args.unused:
            result.findings = [f for f in result.findings if f.kind != "unused_import"]

        if args.output == "tree":
            render_tree(result)
        elif args.output == "mermaid":
            print(render_mermaid(result))
        elif args.output == "dot":
            print(render_dot(result))

        if args.detect_cycles:
            if any(f.kind == "cycle" for f in result.findings):
                sys.exit(1)


if __name__ == "__main__":
    main()
