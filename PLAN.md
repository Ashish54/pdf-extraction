# Plan: PDF Section Extractor (Python)

## 1. Goal

Build a Python CLI tool that:

1. Reads large PDF files efficiently.
2. Loads a YAML config listing the sections (by TOC/bookmark title) to **keep**, plus the document title.
3. Uses the PDF's **embedded bookmarks/outline** to compute each section's page range.
4. Drops every section **not** listed in the config, keeping the front matter (pages before the first bookmark, i.e. cover/title/preface) plus all listed sections **with their subsections**.
5. Writes a new PDF by **copying original pages losslessly** (no re-rendering), preserving selectable text, vector graphics, and metadata.

### Locked-in decisions (from clarifying questions)

| Decision | Choice |
|---|---|
| TOC source | Embedded PDF bookmarks/outline only |
| Config format | YAML |
| Title matching | Normalized exact match (case/whitespace-insensitive) |
| Keep semantics | Front matter + listed sections (subsections included) |
| Output | Copy original pages as-is |
| Missing config entry | Warn and continue |

---

## 2. Tech choices

- **`pypdf`** (primary backend): pure Python, actively maintained, permissive license, lazy page loading so multi-GB / 10k-page files don't need to fit in memory at once.
- **PyYAML** for the config.
- **Optional PyMuPDF (`fitz`) backend** behind a flag for speed benchmarking — note its AGPL license, so pypdf stays the default.
- `argparse` CLI (stdlib), `logging` for warnings, `pytest` for tests.

---

## 3. Project layout

```
pdf_extractor/
├── pyproject.toml
├── README.md
├── config.example.yaml
├── pdf_extractor/
│   ├── __init__.py
│   ├── cli.py            # argument parsing, logging setup, exit codes
│   ├── config.py         # YAML load + schema validation
│   ├── outline.py        # bookmark extraction, flattening, page-range computation
│   ├── matcher.py        # title normalization + config↔outline matching
│   ├── selector.py       # page-set computation (front matter + kept ranges)
│   ├── writer.py         # lossless page copy + rebuilt bookmarks + metadata
│   └── errors.py
└── tests/
    ├── fixtures/         # small synthetic PDFs with known outlines (generated)
    ├── test_outline.py
    ├── test_matcher.py
    ├── test_selector.py
    └── test_e2e.py
```

---

## 4. Config file schema (YAML)

```yaml
# config.example.yaml
title: "Annual Technical Report 2024"   # document title; informational +
                                        # sanity-checked against PDF metadata (warn on mismatch)
on_missing: warn          # warn | fail   (default: warn)
keep_front_matter: true   # pages before the first bookmark (default: true)
sections:                 # exact TOC titles, any nesting level; order irrelevant
  - "Introduction"
  - "Chapter 2: Architecture"
  - "Chapter 5: Benchmarks"
  - "Appendix A: Raw Data"
```

Validation rules:
- `sections` is required and must be a non-empty list of strings.
- Unknown keys → warning (forward-compatible), not an error.
- Duplicate entries after normalization → warning, deduplicated.

---

## 5. Core algorithm

### 5.1 Outline extraction (`outline.py`)

1. Open with `pypdf.PdfReader(path)` (lazy; `strict=False` for tolerant parsing).
2. Walk `reader.outline` recursively — it is a nested list of `Destination` objects and sub-lists.
3. For each bookmark record: `(title, level, start_page)` via `reader.get_destination_page_number(dest)`.
4. Produce a **flat, document-ordered list** of `Section(title, level, start_page)`.
5. Compute each section's **end boundary**: the `start_page` of the next bookmark whose `level <=` this section's level (i.e. next non-descendant), or `total_pages` if none.
   - `page_range = [start_page, end_page)` — because descendants start inside this interval, the range **already includes all subsection pages**, so keeping a parent automatically keeps its children.
6. Handle quirks:
   - Bookmarks pointing at the same page → zero-length range is fine (union handles it).
   - Out-of-order page targets → sort by `start_page`, keep stable order for ties, then compute boundaries.
   - No outline at all → abort with a clear error (decision: bookmarks are the only TOC source).

### 5.2 Matching (`matcher.py`)

Normalization function applied to **both** config titles and bookmark titles:

```python
def normalize(title: str) -> str:
    import unicodedata, re
    t = unicodedata.normalize("NFKD", title)
    t = t.casefold()
    t = re.sub(r"\s+", " ", t).strip()
    return t
```

- Exact match on normalized strings.
- If a normalized config title matches **multiple** bookmarks → keep the first, log a warning listing all matches (page numbers).
- Config entries with no match → warning (or abort if `on_missing: fail`), per locked decision.

### 5.3 Page selection (`selector.py`)

```
kept = set()
if keep_front_matter:
    kept |= range(0, first_bookmark_page)        # cover, title, TOC pages, preface
for each matched section:
    kept |= range(section.start_page, section.end_page)
sorted_page_list = sorted(kept)
```

- Union semantics naturally dedupe overlapping/nested ranges.
- Report to the user: matched sections with original page ranges, total pages kept vs. dropped.

### 5.4 Output (`writer.py`)

1. `PdfWriter()`; for each kept page index: `writer.add_page(reader.pages[i])` (lossless copy — no re-encoding).
2. Copy document metadata (`/Title`, `/Author`, …) from `reader.metadata`.
3. **Rebuild bookmarks** for kept sections: for each kept section, add an outline entry pointing at `new_index = old_page - (# dropped pages before it)`; preserve the kept sections' relative nesting. Dropped sections' bookmarks are omitted; kept children of dropped parents are re-rooted one level up.
4. Optionally `writer.compress_identical_objects()`; write with a temp-file-then-rename pattern to avoid corrupting output on failure.
5. Never modify the input file; refuse `--output` equal to input path.

---

## 6. CLI design

```
pdf-extract CONFIG.yaml INPUT.pdf [-o OUTPUT.pdf]
          [--dry-run]            # print matched sections + page ranges, write nothing
          [--on-missing warn|fail]
          [--no-front-matter]
          [--keep-bookmarks / --no-bookmarks]   # default: keep, rebuilt
          [-v | -q]
```

- `--dry-run` prints a table: config entry → matched bookmark (original title, level, pages X–Y) → kept/dropped. This is the primary debugging tool for config tuning.
- Exit codes: `0` success, `1` config/IO error, `2` missing sections with `on_missing: fail`, `3` PDF has no outline.

---

## 7. Large-file handling

- pypdf loads page objects lazily; per-page `add_page` copies stream references, so peak memory stays roughly proportional to the largest single page, not the file.
- Stream output directly to disk; no intermediate full-document buffer.
- Log progress every N pages (e.g. 500) at `-v`.
- Benchmark target: a 5,000-page / 500 MB synthetic file must complete with < 500 MB RSS. If pypdf falls short in practice, evaluate the optional PyMuPDF backend (`doc.select(kept_pages)` is very fast) behind `--backend pymupdf`.

---

## 8. Edge cases & failure modes

| Case | Behavior |
|---|---|
| PDF has no outline | Hard error, exit code 3 |
| Encrypted PDF | Attempt empty-password decrypt; otherwise clear error |
| Duplicate bookmark titles | First match wins + warning with page numbers |
| Config entry matches nothing | Warn (or fail if `on_missing: fail`) |
| Bookmark page targets out of order | Sort by page before boundary computation |
| Overlapping kept ranges | Set union; output pages appear once, in original order |
| All sections dropped | Refuse to write an empty/front-matter-only PDF without `--force` |
| `title` in config ≠ PDF metadata title | Warning only, processing continues |

---

## 9. Testing plan

1. **Fixture generator** (test utility): build small PDFs with `pypdf` itself — N pages with printed page numbers, nested bookmarks (`Ch1 → 1.1, 1.2; Ch2; …`), plus front-matter pages.
2. **Unit tests**
   - `normalize()`: case, whitespace, unicode accents, punctuation.
   - Range computation: nested levels, siblings on same page, last section to EOF.
   - Selector: front matter on/off, adjacent ranges, full keep, nested keep.
   - Matcher: exact-after-normalization, duplicates, missing entries.
3. **E2E test**: config keeps 2 of 5 chapters → output page count and per-page text verified; bookmarks rebuilt; metadata preserved.
4. **Regression/perf test**: generated 5,000-page file; assert runtime and memory ceiling.
5. **Real-world smoke test** (manual): one large genuine PDF from the user's actual workload.

---

## 10. Implementation milestones

1. **Scaffold** — pyproject, deps (`pypdf`, `PyYAML`, `pytest`), package skeleton, example config.
2. **Config loader + validation** with clear error messages.
3. **Outline extraction + range computation** (`outline.py`) + unit tests.
4. **Matcher + selector** (`matcher.py`, `selector.py`) + unit tests.
5. **Writer** with metadata + rebuilt bookmarks (`writer.py`).
6. **CLI** wiring, `--dry-run`, logging, exit codes.
7. **E2E + perf tests**, README with usage examples.
8. **(Optional)** PyMuPDF backend + benchmark comparison.

---

## 11. Open follow-ups (non-blocking)

- Should the printed TOC **pages themselves** be kept as part of front matter even though they reference dropped sections? (Default: yes — they're front matter.)
- Future: substring/regex matching mode, per-section exclusion lists, splitting kept sections into separate PDFs.

---

## 12. Decisions locked in the grilling round

Resolved via `/grill-with-docs`; these amend earlier sections and are final for v1:

- **Q1 — Bookmarks-only, confirmed**: hard-fail on outline-less PDFs (exit 3), but `outline.py` sits behind a `SectionSource` protocol so a printed-TOC or manual page-range source can be added later without touching matcher/selector/writer. Recorded in `docs/adr/0001-embedded-outline-only.md`.
- **Q2 — Page-granularity leakage accepted**: sections sharing a page leak across keep/drop boundaries; `--dry-run` reports every Boundary Page (with a mid-page heuristic from destination y-offsets) instead of attempting content redaction.
- **Q3 — Printed TOC kept stale**: front matter stays verbatim; the run summary notes the staleness. New config flag `drop_printed_toc: true` drops bookmarked sections titled "Contents"/"Table of Contents". No TOC regeneration (would break lossless copying).
- **Q4 — Back matter kept symmetrically**: pages from the last bookmark's start to EOF are kept even when that final section is dropped (page granularity makes the back cover inseparable), with a loud warning; escape hatch `keep_back_matter: false`.
- **Q5 — Single-input CLI + library API**: `extract(config, in_path, out_path)` is the public function; the CLI is a thin wrapper. Batch support is a future 10-line wrapper. Perf target: 1k–10k pages / 100 MB–1 GB.
- **Q6 — Match-all semantics**: one config entry keeps **every** section with a matching normalized title, with a warning listing all matched pages (over-keeping is recoverable; under-keeping is silent data loss).
- **Q7 — `title:` is documentation + output metadata**: never validated against source metadata (which is unreliable in the wild); it stamps the output PDF's `/Title`.
- Vocabulary captured in `CONTEXT.md` (Section, Section Range, Front/Back Matter, Boundary Page, Kept Set, Printed TOC, Matched Section).
