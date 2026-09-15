# pdf-extractor

Keep only the configured sections of a large PDF and drop the rest — sections
are located via the PDF's **embedded bookmarks (outline)**, and surviving pages
are **copied verbatim** into a new PDF (no re-rendering, text stays selectable,
vector graphics intact). Built for large files: pages stream through one at a
time, so memory stays flat even for multi-hundred-MB documents.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"   # or just: pip install pypdf PyYAML
```

## Usage

```bash
pdf-extract config.yaml input.pdf -o output.pdf
# or without installing:
python -m pdf_extractor.cli config.yaml input.pdf -o output.pdf
```

Always start with a dry run — it writes nothing and shows exactly which
sections matched, which pages survive, and where boundary pages may leak
content across a keep/drop edge:

```bash
pdf-extract config.yaml input.pdf --dry-run
```

## Config (YAML)

```yaml
title: "Annual Technical Report 2024"  # documentation; stamps output /Title
on_missing: warn          # warn | fail — when a config entry matches no bookmark
keep_front_matter: true   # pages before the first bookmark (cover, title, printed TOC)
keep_back_matter: true    # trailing pages of a dropped final section (see semantics)
drop_printed_toc: false   # drop bookmarked sections titled Contents/Table of Contents
sections:                 # exact bookmark titles, case/whitespace-insensitive
  - "Introduction"
  - "Chapter 2: Architecture"
  - "Appendix A: Raw Data"
```

CLI overrides: `--on-missing`, `--no-front-matter`, `--no-back-matter`,
`--drop-printed-toc`, `--no-bookmarks`, `--force`, `--dry-run`.

## Semantics (the important part)

- **Section range**: from a bookmark's page to the next bookmark at the same
  or higher level. Keeping a section **always keeps its subsections**.
- **Match-all**: one config entry keeps *every* section with that title
  (real documents repeat "Exercises", "Summary", …). A warning lists them.
- **Front matter** (before the first bookmark) and **back matter** (from the
  last bookmark to EOF, when that final section is dropped) are kept by
  default. Back matter is kept *with its section's content* — page granularity
  makes the back cover inseparable — and the tool says so in a warning.
- **Boundary pages**: if a dropped section ends and a kept one begins on the
  same page, that page may show both. `--dry-run` prints every such boundary;
  page-level copying cannot split a page.
- **Printed TOC staleness**: front matter is copied verbatim, so a printed
  table of contents still lists dropped sections with original page numbers.
  Use `drop_printed_toc: true` to remove bookmarked TOC sections.
- The input file is never modified; output == input is refused.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | config / IO / extraction error |
| 2 | missing sections with `on_missing: fail` |
| 3 | PDF has no embedded outline |

A PDF without bookmarks is rejected (exit 3) — see
[`docs/adr/0001-embedded-outline-only.md`](../docs/adr/0001-embedded-outline-only.md).

## Library use

```python
from pdf_extractor import extract, load_config

config = load_config("config.yaml")
report = extract(config, "input.pdf", "output.pdf")
print(report.kept_pages, report.selection.boundaries)
```

## Development

```bash
.venv/bin/python -m pytest        # from this directory
```

Tests build synthetic PDFs with pypdf itself; each page carries a unique
mediabox width so tests can verify exactly which original pages survive.
