"""Library entry point: extract(config, input_path, output_path, ...)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from .config import ExtractConfig
from .errors import (
    EmptySelectionError,
    ExtractorError,
    MissingSectionsError,
    OutputPathError,
)
from .matcher import MatchResult, find_printed_toc, match_sections
from .outline import OutlineSource, SectionSource
from .selector import Selection, compute_selection
from .writer import write_pdf

logger = logging.getLogger(__name__)


@dataclass
class ExtractReport:
    """Everything a run decided, for CLI display or programmatic inspection."""

    input_path: Path
    output_path: Path | None
    total_pages: int
    kept_pages: list[int]
    match: MatchResult
    selection: Selection
    dry_run: bool = False

    @property
    def dropped_count(self) -> int:
        return self.total_pages - len(self.kept_pages)


def extract(
    config: ExtractConfig,
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    dry_run: bool = False,
    keep_bookmarks: bool = True,
    force: bool = False,
    source: SectionSource | None = None,
) -> ExtractReport:
    """Extract the configured sections of input_path into output_path.

    With dry_run=True, compute and report everything but write nothing.
    The SectionSource defaults to the embedded outline (ADR 0001).
    """
    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(f"Input PDF not found: {input_path}")

    reader = PdfReader(str(input_path), strict=False)
    if reader.is_encrypted:
        try:
            result = reader.decrypt("")
        except Exception as exc:
            raise ExtractorError(f"PDF is encrypted and could not be opened: {exc}") from exc
        if int(result) == 0:
            raise ExtractorError("PDF is encrypted; empty-password decrypt failed")
    total_pages = len(reader.pages)

    sections = (source or OutlineSource()).load(reader)

    match = match_sections(config.sections, sections)
    if match.unmatched and config.on_missing == "fail":
        raise MissingSectionsError(match.unmatched)

    toc = find_printed_toc(sections) if config.drop_printed_toc else []
    selection = compute_selection(
        sections,
        match.sections,
        total_pages,
        keep_front_matter=config.keep_front_matter,
        keep_back_matter=config.keep_back_matter,
        toc_sections=toc,
    )

    if not selection.pages and not force:
        raise EmptySelectionError(
            "Nothing left to keep (all sections dropped); "
            "pass force=True / --force to allow an empty result"
        )

    out_path: Path | None = None
    if not dry_run:
        out_path = Path(output_path) if output_path else _default_output(input_path)
        if os.path.abspath(out_path) == os.path.abspath(input_path):
            raise OutputPathError(f"Refusing to overwrite input file: {input_path}")
        # Every section whose start page survives gets a rebuilt outline entry
        # (matched sections AND their kept descendants; children of dropped
        # parents are re-rooted by the writer).
        surviving = set(selection.pages)
        outline_sections = [s for s in sections if s.start_page in surviving]
        write_pdf(
            reader,
            selection.pages,
            out_path,
            title=config.title,
            kept_sections=outline_sections,
            keep_bookmarks=keep_bookmarks,
        )

    return ExtractReport(
        input_path=input_path,
        output_path=out_path,
        total_pages=total_pages,
        kept_pages=selection.pages,
        match=match,
        selection=selection,
        dry_run=dry_run,
    )


def _default_output(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}.extracted.pdf")
