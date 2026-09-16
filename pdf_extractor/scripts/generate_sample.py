#!/usr/bin/env python3
"""Generate a realistic sample PDF + config for trying out pdf-extract.

Usage: python scripts/generate_sample.py [pages] [out_dir]
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from pypdf import PdfWriter


def main() -> None:
    pages = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("sample")
    out_dir.mkdir(parents=True, exist_ok=True)

    writer = PdfWriter()
    for i in range(pages):
        writer.add_blank_page(width=612, height=792)

    # Front matter: pages 0-3 (cover, title, printed TOC, preface).
    outline: list[tuple[str, int, int]] = [
        ("Contents", 0, 2),
        ("Introduction", 0, 4),
    ]
    chapters = max(2, (pages - 204) // 100)
    for ch in range(1, chapters + 1):
        start = 104 + (ch - 1) * 100  # Introduction owns pages 4-103
        outline.append((f"Chapter {ch}: Topic {ch}", 0, start))
        for sub in range(1, 4):
            outline.append((f"{ch}.{sub} Details", 1, start + sub * 25))
        outline.append(("Exercises", 1, start + 90))
    outline.append(("Appendix A: Raw Data", 0, pages - 100))
    outline.append(("Index", 0, pages - 20))

    stack: list[tuple[int, object]] = []
    for title, level, page in outline:
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else None
        item = writer.add_outline_item(title, page, parent=parent)
        stack.append((level, item))

    writer.add_metadata({"/Title": "Sample Big Report", "/Author": "pdf-extractor"})
    pdf_path = out_dir / "sample.pdf"
    with open(pdf_path, "wb") as fh:
        writer.write(fh)

    config = {
        "input_dir": str(out_dir),
        "output_dir": str(out_dir / "out"),
        "sections": [
            "Introduction",
            "Chapter 2: Topic 2",
            "Exercises",
            "Appendix A: Raw Data",
        ],
        "drop_printed_toc": True,
    }
    config_path = out_dir / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    size_mb = pdf_path.stat().st_size / 1e6
    print(f"Wrote {pdf_path} ({pages} pages, {size_mb:.1f} MB)")
    print(f"Wrote {config_path}")
    print(f"\nTry:\n  python -m pdf_extractor.cli {config_path} sample.pdf --dry-run")


if __name__ == "__main__":
    main()
