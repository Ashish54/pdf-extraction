"""Shared fixtures: synthetic PDFs with known outlines.

Page identity trick: page i is created with mediabox width 600+i, so tests can
read an extracted PDF and know exactly which original pages survived.
"""

from __future__ import annotations

import pytest
from pypdf import PdfWriter

STANDARD_PAGES = 20
STANDARD_OUTLINE = [
    # (title, level, start_page) — ranges become:
    # Intro [2,4) Ch1 [4,8) 1.1 [5,7) 1.2 [7,8) Ch2 [8,12) Ch3 [12,16) App [16,20)
    ("Introduction", 0, 2),
    ("Chapter 1", 0, 4),
    ("Section 1.1", 1, 5),
    ("Section 1.2", 1, 7),
    ("Chapter 2", 0, 8),
    ("Chapter 3", 0, 12),
    ("Appendix", 0, 16),
]


def build_pdf(path, num_pages, outline_spec=()):
    writer = PdfWriter()
    for i in range(num_pages):
        writer.add_blank_page(width=600 + i, height=800)
    stack = []
    for title, level, page in outline_spec:
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else None
        item = writer.add_outline_item(title, page, parent=parent)
        stack.append((level, item))
    with open(path, "wb") as fh:
        writer.write(fh)
    return path


def page_ids(pdf_path):
    """Original page indexes surviving in pdf_path, via mediabox widths."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return [int(float(p.mediabox.width)) - 600 for p in reader.pages]


def outline_titles(reader):
    """Flat list of (title, level) from a reader's outline."""
    out = []

    def walk(items, level):
        for item in items:
            if isinstance(item, list):
                walk(item, level + 1)
            else:
                out.append((item.title, level))

    walk(reader.outline, 0)
    return out


@pytest.fixture
def pdf_factory(tmp_path):
    counter = {"n": 0}

    def make(num_pages=STANDARD_PAGES, outline_spec=STANDARD_OUTLINE, name=None):
        counter["n"] += 1
        path = tmp_path / (name or f"sample{counter['n']}.pdf")
        return build_pdf(path, num_pages, outline_spec)

    return make


@pytest.fixture
def config_factory(tmp_path):
    import yaml

    counter = {"n": 0}

    def make(**overrides):
        counter["n"] += 1
        data = {"sections": ["Chapter 1"]}
        data.update(overrides)
        path = tmp_path / f"config{counter['n']}.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return path

    return make
