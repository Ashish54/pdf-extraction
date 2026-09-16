"""Compute the Kept Set: which original pages survive extraction."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .outline import Section

logger = logging.getLogger(__name__)


@dataclass
class BoundaryNote:
    """A page where kept and dropped Sections may share paper.

    Page-granular extraction cannot split a page: a Boundary Page may visibly
    contain tail content of a dropped Section (or lose head content of a kept
    one). Accepted limitation — reported, never silently ignored.
    """

    page: int  # 0-based page where the later Section starts
    before: str  # title of the Section/content ending at this page
    after: str  # title of the Section starting here
    kept_before: bool
    kept_after: bool
    mid_page: bool  # destination y-offset suggests a mid-page start


@dataclass
class Selection:
    pages: list[int]  # the Kept Set: sorted, unique, 0-based
    front_matter: range
    back_matter: range | None = None
    back_matter_section: Section | None = None  # dropped final Section, if kept anyway
    toc_dropped: list[Section] = field(default_factory=list)
    boundaries: list[BoundaryNote] = field(default_factory=list)


def compute_selection(
    sections: list[Section],
    kept_sections: list[Section],
    total_pages: int,
    *,
    keep_front_matter: bool = True,
    keep_back_matter: bool = True,
    toc_sections: list[Section] | None = None,
) -> Selection:
    if not sections:
        raise ValueError("compute_selection requires at least one section")

    kept_set: set[int] = set()

    first_start = min(s.start_page for s in sections)
    front = range(0, first_start) if keep_front_matter else range(0, 0)
    kept_set.update(front)

    kept_ids = {id(s) for s in kept_sections}
    for s in kept_sections:
        kept_set.update(range(s.start_page, s.end_page))

    # Back matter: the final outline Section's range, kept even when that
    # Section is dropped — its tail (colophon, back cover) is page-granularly
    # inseparable from its content, so we keep the pages and say so loudly.
    last = max(sections, key=lambda s: s.start_page)
    back: range | None = None
    back_section: Section | None = None
    if id(last) not in kept_ids and keep_back_matter and last.end_page > last.start_page:
        back = range(last.start_page, last.end_page)
        back_section = last
        kept_set.update(back)
        logger.warning(
            "Back matter pages %d-%d kept although final section %r is dropped; "
            "those pages include its content (page-granularity limit)",
            last.start_page + 1,
            last.end_page,
            last.title,
        )

    toc_dropped: list[Section] = []
    for s in toc_sections or []:
        toc_dropped.append(s)
        kept_set.difference_update(range(s.start_page, s.end_page))
        logger.warning(
            "Printed TOC section %r (pages %d-%d) dropped",
            s.title,
            s.start_page + 1,
            s.end_page,
        )

    pages = sorted(kept_set)
    page_set = set(pages)

    # Boundary Pages: keep-status flips at a Section start page.
    boundaries: list[BoundaryNote] = []
    ordered = sorted(sections, key=lambda s: (s.start_page, s.level))
    for cur in ordered:
        p = cur.start_page
        if p == 0:
            continue
        kept_before = (p - 1) in page_set
        kept_after = p in page_set
        if kept_before == kept_after:
            continue
        before = next(
            (s.title for s in reversed(ordered) if s.end_page == p and s is not cur),
            "front matter",
        )
        boundaries.append(
            BoundaryNote(
                page=p,
                before=before,
                after=cur.title,
                kept_before=kept_before,
                kept_after=kept_after,
                mid_page=cur.mid_page_hint,
            )
        )

    return Selection(
        pages=pages,
        front_matter=front,
        back_matter=back,
        back_matter_section=back_section,
        toc_dropped=toc_dropped,
        boundaries=boundaries,
    )
