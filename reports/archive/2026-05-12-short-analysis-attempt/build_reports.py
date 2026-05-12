#!/usr/bin/env python3
"""Render the refreshed markdown reports to PDF with pandoc."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = [
    "01-executive-brief.md",
    "02-local-vs-upstream-gap-analysis.md",
    "03-connector-and-partner-update.md",
    "04-migration-roadmap.md",
]


def render(markdown_name: str) -> None:
    src = ROOT / markdown_name
    dest = src.with_suffix(".pdf")
    cmd = [
        "pandoc",
        str(src),
        "--standalone",
        "--from",
        "markdown+pipe_tables+table_captions",
        "--pdf-engine=xelatex",
        "--toc",
        "--number-sections",
        "-V",
        "geometry:margin=0.9in",
        "-V",
        "fontsize=11pt",
        "-V",
        "mainfont=Times New Roman",
        "-V",
        "colorlinks=true",
        "-V",
        "urlcolor=blue",
        "-o",
        str(dest),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    if shutil.which("pandoc") is None:
        raise SystemExit("pandoc is required to build the report PDFs")
    if shutil.which("xelatex") is None:
        raise SystemExit("xelatex is required to build the report PDFs")

    for report in REPORTS:
        render(report)


if __name__ == "__main__":
    main()
