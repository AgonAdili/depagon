"""Command-line entry point for depagon."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from depagon.analyzer import Analyzer
from depagon.renderers import render_dot, render_html, render_json, render_mermaid, render_tree


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="depagon",
        description="Analyze the import dependency structure of a Python project.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Scan a Python project directory.")
    scan.add_argument("path", type=Path, help="Path to the project root to analyze.")
    scan.add_argument(
        "--output",
        choices=["tree", "mermaid", "dot", "json", "html"],
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
    """Entry point wired to the ``depagon`` console-script."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "scan":
        root = args.path.resolve()
        if not root.is_dir():
            print(f"Error: '{root}' is not a directory.", file=sys.stderr)
            sys.exit(1)

        result = Analyzer().analyze(root, show_progress=True)

        if not args.unused:
            result.findings = [f for f in result.findings if f.kind != "unused_import"]

        if args.output == "tree":
            render_tree(result)
        elif args.output == "mermaid":
            print(render_mermaid(result))
        elif args.output == "dot":
            print(render_dot(result))
        elif args.output == "json":
            print(render_json(result))
        elif args.output == "html":
            print(render_html(result))

        if args.detect_cycles:
            if any(f.kind == "cycle" for f in result.findings):
                sys.exit(1)


if __name__ == "__main__":
    main()
