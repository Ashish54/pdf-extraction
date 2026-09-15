"""Command-line interface: pdf-extract CONFIG.yaml INPUT.pdf [-o OUT.pdf]"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace

from .api import ExtractReport, extract
from .config import load_config
from .errors import (
    ConfigError,
    ExtractorError,
    MissingSectionsError,
    NoOutlineError,
)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_MISSING = 2
EXIT_NO_OUTLINE = 3


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pdf-extract",
        description=(
            "Keep only the sections listed in a YAML config, located via the "
            "PDF's embedded bookmarks; pages are copied losslessly."
        ),
    )
    p.add_argument("config", help="YAML config file")
    p.add_argument("input", help="input PDF")
    p.add_argument(
        "-o", "--output", help="output PDF (default: <input>.extracted.pdf)"
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print matched sections, page ranges and boundary pages; write nothing",
    )
    p.add_argument("--on-missing", choices=("warn", "fail"), help="override config")
    p.add_argument("--no-front-matter", action="store_true", help="drop pages before the first bookmark")
    p.add_argument("--no-back-matter", action="store_true", help="drop trailing pages of a dropped final section")
    p.add_argument(
        "--drop-printed-toc",
        action="store_true",
        help="drop bookmarked sections titled Contents / Table of Contents",
    )
    p.add_argument("--no-bookmarks", action="store_true", help="do not rebuild the outline in the output")
    p.add_argument("--force", action="store_true", help="allow an empty selection")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("-q", "--quiet", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    level = (
        logging.DEBUG if args.verbose else logging.WARNING if args.quiet else logging.INFO
    )
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")

    try:
        config = load_config(args.config)
        if args.on_missing:
            config = replace(config, on_missing=args.on_missing)
        if args.no_front_matter:
            config = replace(config, keep_front_matter=False)
        if args.no_back_matter:
            config = replace(config, keep_back_matter=False)
        if args.drop_printed_toc:
            config = replace(config, drop_printed_toc=True)

        report = extract(
            config,
            args.input,
            args.output,
            dry_run=args.dry_run,
            keep_bookmarks=not args.no_bookmarks,
            force=args.force,
        )
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except NoOutlineError as exc:
        print(f"No outline: {exc}", file=sys.stderr)
        return EXIT_NO_OUTLINE
    except MissingSectionsError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_MISSING
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except ExtractorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    _print_report(report)
    return EXIT_OK


def _print_report(report: ExtractReport) -> None:
    m, sel = report.match, report.selection
    print(f"Input : {report.input_path} ({report.total_pages} pages)")
    if report.dry_run:
        print("Mode  : dry-run (nothing written)")
    else:
        print(f"Output: {report.output_path}")

    fm = sel.front_matter
    if len(fm):
        print(f"Front matter kept: pages {fm.start + 1}-{fm.stop} ({len(fm)} pages)")
        if not sel.toc_dropped:
            print(
                "  note: front matter is verbatim — any printed TOC in it still "
                "lists dropped sections with original page numbers"
            )

    for entry, hits in m.matched.items():
        for s in hits:
            print(
                f"KEEP  {entry!r} -> {s.title!r} "
                f"(level {s.level}, pages {s.start_page + 1}-{s.end_page})"
            )
    for entry in m.unmatched:
        print(f"MISS  {entry!r} (no outline match)")
    for s in sel.toc_dropped:
        print(f"TOC   dropped printed TOC {s.title!r} (pages {s.start_page + 1}-{s.end_page})")

    if sel.back_matter is not None and sel.back_matter_section is not None:
        bm = sel.back_matter
        print(
            f"Back matter kept: pages {bm.start + 1}-{bm.stop} "
            f"(starts at dropped final section {sel.back_matter_section.title!r}; "
            f"includes its content)"
        )

    for b in sel.boundaries:
        where = "mid-page start" if b.mid_page else "page boundary"
        direction = "kept" if b.kept_after else "dropped"
        print(
            f"BOUNDARY page {b.page + 1}: {b.before!r} -> {b.after!r} "
            f"({direction}, {where}; page may contain content of both sections)"
        )

    print(
        f"Pages kept {len(report.kept_pages)} / {report.total_pages} "
        f"({report.dropped_count} dropped)"
    )


if __name__ == "__main__":
    sys.exit(main())
