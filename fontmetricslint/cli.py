"""Command line entry point for the AFM metrics linter."""

from __future__ import annotations

import argparse
import sys
from typing import Iterable, List, Optional

from .linter import Finding, lint_stream


def _lint_file(path: str) -> Iterable[Finding]:
    if path == "-":
        yield from lint_stream(sys.stdin)
        return
    # AFM files are specified as Latin-1 (StandardEncoding derives from it),
    # and opening in text mode here still gives us line-by-line iteration
    # without reading the file into memory up front.
    with open(path, "r", encoding="latin-1") as handle:
        yield from lint_stream(handle)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="afm-lint",
        description="Lint Adobe Font Metrics (.afm) files and report findings with line numbers.",
    )
    parser.add_argument(
        "paths", nargs="+", metavar="FILE",
        help="AFM file(s) to check, or '-' for stdin",
    )
    args = parser.parse_args(argv)

    had_error = False
    for path in args.paths:
        for finding in _lint_file(path):
            print(f"{path}:{finding.line}: {finding.code} {finding.severity}: {finding.message}")
            if finding.severity == "error":
                had_error = True

    return 1 if had_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
