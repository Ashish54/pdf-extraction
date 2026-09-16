# Runbook — PDF Section Extractor

How to install, run, and troubleshoot `pdf-extract`. All commands assume the
workspace root (`/Users/ashish/Desktop/Utility`) unless noted.

## 1. Prerequisites

- Python 3.11+ (3.13 verified)
- Dependencies already installed in the workspace venv: `.venv/`
  (pypdf 6.x, PyYAML, pytest). To recreate from scratch:

```bash
python3 -m venv .venv
.venv/bin/pip install pypdf pyyaml pytest
```

## 2. Prepare a config

Copy the example and edit the section list to match your document's bookmark
titles exactly (matching itself is case/whitespace-insensitive):

```bash
cp pdf_extractor/config.example.yaml myconfig.yaml
```

```yaml
input_dir: "./pdfs/in"        # your PDFs live here
output_dir: "./pdfs/out"      # reduced PDFs are written here
# title: "Custom Title"       # optional; default = input file name
on_missing: warn              # warn | fail
keep_front_matter: true       # pages before the first bookmark
keep_back_matter: true        # trailing pages of a dropped final section
drop_printed_toc: false       # drop bookmarked "Contents"/"Table of Contents"
sections:
  - "Introduction"
  - "Chapter 2: Architecture"
```

## 3. ALWAYS dry-run first

Writes nothing; shows what matched, what survives, and where pages may leak.
Pass **just the file name** — it is resolved inside `input_dir`:

```bash
cd pdf_extractor
../.venv/bin/python -m pdf_extractor.cli ../myconfig.yaml annual_report.pdf --dry-run
```

Read the output before proceeding:

| Line | Meaning |
|---|---|
| `KEEP 'X' -> 'Y' (level L, pages A-B)` | Config entry matched; pages A–B kept (subsections included) |
| `KEEP` repeated for one entry | Match-all: several sections share the title; all kept (warning too) |
| `MISS 'X'` | No bookmark matched — fix the config spelling, or it stays out |
| `TOC dropped...` | `drop_printed_toc` removed a bookmarked Contents section |
| `Back matter kept...` | Final section is dropped but its pages kept (may contain its content) |
| `BOUNDARY page N` | Kept and dropped sections share paper at page N — inspect that page |

## 4. Run the extraction

```bash
../.venv/bin/python -m pdf_extractor.cli ../myconfig.yaml annual_report.pdf
```

- Output goes to **`<output_dir>/annual_report_reduced.pdf`** automatically;
  `-o some/where.pdf` overrides it.
- The output PDF's `/Title` metadata is the file name (`annual_report`);
  set `title:` in config to override.
- The input file is **never modified**; pointing `-o` at the input is refused.
- Optional: install the package once (`../.venv/bin/pip install -e .` from
  `pdf_extractor/`) to get a `pdf-extract` command instead of `python -m ...`.

### CLI flags

| Flag | Effect |
|---|---|
| `--dry-run` | Report only, write nothing |
| `-o PATH` | Override the default `<output_dir>/<name>_reduced.pdf` |
| `--on-missing warn\|fail` | Override config |
| `--no-front-matter` | Drop pages before the first bookmark |
| `--no-back-matter` | Drop trailing pages of a dropped final section |
| `--drop-printed-toc` | Drop bookmarked Contents/TOC sections |
| `--no-bookmarks` | Don't rebuild the outline in the output |
| `--force` | Allow an empty result |
| `-v` / `-q` | Verbose / quiet logging |

## 5. Exit codes & responses

| Code | Cause | Response |
|---|---|---|
| 0 | Success | Check the summary line (`Pages kept X / Y`) against the dry-run |
| 1 | Config or IO error | Read the message: bad YAML, missing file, output == input, empty selection (use `--force` if intended) |
| 2 | `on_missing: fail` and a config entry matched nothing | Fix the title in config, or relax to `warn` |
| 3 | PDF has no embedded outline | **This tool cannot process that file** (ADR 0001). Confirm with `mutool show file.pdf outline` or any PDF viewer's bookmark panel; a printed-TOC fallback is a planned v2 feature |

## 6. Warnings you will see (all by design)

- **"matched N outline entries; all kept"** — match-all on a repeated title.
  Over-keeping is safe; remove entries to keep less.
- **"Back matter pages A-B kept although final section is dropped"** — the
  back cover is page-inseparable from that section; use `--no-back-matter`.
- **"front matter is verbatim — printed TOC still lists original pages"** —
  expected; use `drop_printed_toc: true` if the TOC is bookmarked.
- **BOUNDARY lines** — page-granularity limit, not a bug. If a boundary page
  shows content you can't ship, that document needs content redaction, which
  this tool deliberately does not do.

## 7. Try it without a real PDF

```bash
cd pdf_extractor
../.venv/bin/python scripts/generate_sample.py 5000 sample
../.venv/bin/python -m pdf_extractor.cli sample/config.yaml sample.pdf --dry-run
../.venv/bin/python -m pdf_extractor.cli sample/config.yaml sample.pdf
# -> writes sample/out/sample_reduced.pdf
```

## 8. Run the tests

```bash
cd pdf_extractor
../.venv/bin/python -m pytest -q     # expect: 45 passed
```

## 9. Library usage

```python
from pdf_extractor import extract, load_config

config = load_config("myconfig.yaml")
report = extract(config, "annual_report.pdf", dry_run=True)  # resolved in input_dir
for b in report.selection.boundaries:
    print("leak risk at page", b.page + 1)
```
