"""Lossless page-copy writer.

Pages are copied verbatim (no re-encoding or re-rendering), metadata carried
across, and the outline rebuilt for kept Sections with corrected page offsets.
Kept children of dropped parents are re-rooted to their nearest kept ancestor.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from .errors import OutputPathError
from .outline import Section

logger = logging.getLogger(__name__)

_PROGRESS_EVERY = 500


def write_pdf(
    reader: PdfReader,
    pages: list[int],
    out_path: str | Path,
    *,
    title: str | None = None,
    kept_sections: list[Section] | None = None,
    keep_bookmarks: bool = True,
) -> None:
    out_path = Path(out_path)
    in_name = getattr(getattr(reader, "stream", None), "name", None)
    if in_name and os.path.abspath(in_name) == os.path.abspath(out_path):
        raise OutputPathError(f"Refusing to overwrite input file: {in_name}")

    writer = PdfWriter()
    total = len(pages)
    for n, page_index in enumerate(pages, 1):
        writer.add_page(reader.pages[page_index])
        if n % _PROGRESS_EVERY == 0 or n == total:
            logger.info("Copied %d/%d pages", n, total)

    # Metadata: carry the source across; the configured title stamps /Title
    # (it is documentation + output metadata, never validated against source).
    meta = {k: str(v) for k, v in dict(reader.metadata or {}).items() if v is not None}
    if title:
        meta["/Title"] = title
    if meta:
        writer.add_metadata(meta)

    if keep_bookmarks and kept_sections:
        _rebuild_outline(writer, pages, kept_sections)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=out_path.parent, prefix=out_path.stem + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            writer.write(fh)
        os.replace(tmp, out_path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    logger.info("Wrote %s (%d pages)", out_path, len(pages))


def _rebuild_outline(
    writer: PdfWriter, pages: list[int], kept_sections: list[Section]
) -> None:
    new_index = {old: new for new, old in enumerate(pages)}
    stack: list[tuple[int, object]] = []  # (level, outline item) parent stack
    for s in sorted(kept_sections, key=lambda s: (s.start_page, s.level)):
        if s.start_page not in new_index:
            continue  # Section's pages were dropped (e.g. printed-TOC removal)
        while stack and stack[-1][0] >= s.level:
            stack.pop()
        parent = stack[-1][1] if stack else None
        item = writer.add_outline_item(s.title, new_index[s.start_page], parent=parent)
        stack.append((s.level, item))
