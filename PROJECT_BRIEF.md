# Project Brief — PDF Section Extractor

## What it is

A Python CLI + library that shrinks large PDFs to just the sections you care
about. You list the sections to **keep** in a YAML config; the tool locates
each section's pages via the PDF's **embedded bookmarks (outline)**, drops
everything else, and writes a new PDF by **copying the surviving pages
verbatim** — no re-rendering, text stays selectable, graphics stay vector,
memory stays flat even for multi-hundred-MB files.

## Problem

Large reports/books (1k–10k pages, 100 MB–1 GB) are routinely shared in full
when only a handful of chapters are relevant. Manual extraction in a PDF
viewer is error-prone and doesn't scale; text-extraction pipelines destroy
layout. This tool automates chapter-level extraction while preserving the
original pages exactly.

## Goals / non-goals

**Goals**
- Lossless output: kept pages are byte-identical copies.
- Section lookup driven by the document's own outline, not fragile text parsing.
- Auditable: `--dry-run` shows every matched section, kept/dropped page, and
  risky boundary page before anything is written.
- Streaming performance: memory proportional to the largest page, not the file.

**Non-goals (v1)**
- PDFs without embedded bookmarks → rejected with exit code 3 (see ADR 0001;
  a printed-TOC parser can be added behind the existing `SectionSource` seam).
- Splitting pages: sections sharing a physical page leak across the keep/drop
  edge — detected and reported, not redacted.
- Regenerating the printed table of contents (kept front matter stays verbatim;
  optionally the bookmarked TOC section can be dropped).

## Key decisions (locked via design grilling)

| Decision | Choice |
|---|---|
| Section source | Embedded outline only; hard-fail (exit 3) otherwise |
| Config | YAML; `sections` list + `title` + behavior flags |
| Title matching | Normalized exact (case/whitespace-insensitive), **match-all** on duplicates |
| Keep semantics | Front matter + back matter kept by default; keeping a section keeps its subsections |
| Output | Lossless page copy; metadata preserved; config `title:` stamps output `/Title`; outline rebuilt for surviving sections |
| Missing config entry | Warn and continue (`on_missing: fail` to make it fatal) |
| Leakage at shared pages | Accepted; every boundary page reported |

Full rationale: [`PLAN.md`](./PLAN.md) §12, [`CONTEXT.md`](./CONTEXT.md) (domain
glossary), [`docs/adr/0001-embedded-outline-only.md`](./docs/adr/0001-embedded-outline-only.md).

## Architecture

```
config.yaml ──> config.py ──> ExtractConfig
                                  │
input.pdf ──> outline.py ──> list[Section]   (SectionSource protocol)
                                  │
              matcher.py  ──> MatchResult     (normalized, match-all)
                                  │
              selector.py ──> Selection       (Kept Set + BoundaryNotes)
                                  │
              writer.py   ──> output.pdf      (lossless copy, rebuilt outline)

api.py orchestrates; cli.py is a thin wrapper (exit codes 0/1/2/3).
```

## Status

v1 complete. **39/39 tests pass** (synthetic PDFs with page-identity tracking).
Smoke test: 5,000-page PDF → 858 pages extracted in **0.84 s** on an M-series
Mac. Code lives in [`pdf_extractor/`](./pdf_extractor/), with its own
[`README.md`](./pdf_extractor/README.md) covering config and semantics in
detail.

## Next steps

- Validate against a real target PDF (`--dry-run`); if it exits 3, the
  printed-TOC fallback becomes the v2 headline feature.
- Optional: PyMuPDF backend benchmark, batch mode (folder + shared config).
