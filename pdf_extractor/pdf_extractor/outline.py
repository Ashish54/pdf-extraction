"""Section extraction from the PDF's embedded outline (bookmarks).

This is the only SectionSource implemented in v1 (see ADR 0001). A printed-TOC
parser or manual page-range source can be added behind the same protocol
without touching matching, selection, or writing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from pypdf import PdfReader
from pypdf.generic import Destination

from .errors import NoOutlineError

logger = logging.getLogger(__name__)

# A destination whose y-offset is below this fraction of the page height is
# treated as starting mid-page (heuristic for Boundary Page reporting).
_MID_PAGE_FRACTION = 0.85


@dataclass
class Section:
    """One outline entry and the Section Range its content occupies."""

    title: str
    level: int  # 0 = top level
    start_page: int  # 0-based, inclusive
    end_page: int = -1  # 0-based, exclusive; covers all descendants
    mid_page_hint: bool = False  # destination suggests a mid-page start

    @property
    def page_count(self) -> int:
        return self.end_page - self.start_page


class SectionSource(Protocol):
    """Anything that can turn an open PDF into an ordered list of Sections."""

    def load(self, reader: PdfReader) -> list[Section]: ...


class OutlineSource:
    """Reads the embedded outline and computes each Section Range."""

    def load(self, reader: PdfReader) -> list[Section]:
        flat = self._flatten(reader)
        if not flat:
            raise NoOutlineError(
                "PDF has no embedded outline (bookmarks); cannot locate sections"
            )
        self._check_order(flat)
        self._compute_ranges(flat, len(reader.pages))
        return flat

    def _flatten(self, reader: PdfReader) -> list[Section]:
        flat: list[Section] = []

        def walk(items: object, level: int) -> None:
            if not isinstance(items, list):
                return
            for item in items:
                if isinstance(item, list):
                    walk(item, level + 1)
                elif isinstance(item, Destination):
                    page = reader.get_destination_page_number(item)
                    if page is None or page < 0:
                        logger.warning(
                            "Bookmark %r has no usable page target; skipped", item.title
                        )
                        continue
                    flat.append(
                        Section(
                            title=(item.title or "").strip(),
                            level=level,
                            start_page=page,
                            mid_page_hint=self._mid_page(reader, item, page),
                        )
                    )
                else:
                    logger.warning(
                        "Unsupported outline item of type %s skipped",
                        type(item).__name__,
                    )

        try:
            outline = reader.outline
        except Exception as exc:  # malformed outlines exist in the wild
            raise NoOutlineError(f"Could not read PDF outline: {exc}") from exc
        walk(outline, 0)
        return flat

    @staticmethod
    def _mid_page(reader: PdfReader, dest: Destination, page: int) -> bool:
        try:
            if dest.top is None:
                return False
            height = float(reader.pages[page].mediabox.height)
            return height > 0 and float(dest.top) < _MID_PAGE_FRACTION * height
        except Exception:
            return False

    @staticmethod
    def _check_order(flat: list[Section]) -> None:
        for prev, cur in zip(flat, flat[1:]):
            if cur.start_page < prev.start_page:
                logger.warning(
                    "Outline targets out of order: %r (page %d) precedes %r (page %d)",
                    prev.title,
                    prev.start_page + 1,
                    cur.title,
                    cur.start_page + 1,
                )

    @staticmethod
    def _compute_ranges(flat: list[Section], total_pages: int) -> None:
        """Section Range = [start_page, next same-or-higher level start), clamped."""
        for i, section in enumerate(flat):
            end = total_pages
            for later in flat[i + 1 :]:
                if later.level <= section.level:
                    end = max(later.start_page, section.start_page)
                    break
            section.end_page = end
