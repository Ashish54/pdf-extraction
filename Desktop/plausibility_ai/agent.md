# agent.md — AI Agent Guidelines & Architecture Manual

This guide outlines rules, architecture context, and operational instructions for AI Coding Agents operating within the **Plausibility AI** repository.

---

## 1. Core Mission & Repository Overview

**Plausibility AI** provides automated triage and validation commentary for financial risk model plausibility test breaches.

- **Inputs:**
  - Excel Plausibility Test Reports containing breached validation rules.
  - Risk Model Documentation (PDFs) located in `data/model-docs/`.
  - Risk Model Source Code (Python) located in `data/codebase/`.
- **Outputs:**
  - Annotated Excel files containing AI severity ratings, root-cause commentary, cited document/code evidence, confidence metrics, and human reviewer workflow columns.
  - Priority summary sheets for low-confidence items and critical breaches.

---

## 2. Technical Stack & Key Modules

| Layer | Primary Technologies | Key Files |
|---|---|---|
| **CLI / Entry** | `click`, `rich` | [src/cli.py](file:///Users/ashish/Desktop/plausibility_ai/src/cli.py) |
| **Config System** | `PyYAML`, `@dataclass` | [src/config.py](file:///Users/ashish/Desktop/plausibility_ai/src/config.py), [src/config/config.yaml](file:///Users/ashish/Desktop/plausibility_ai/src/config/config.yaml) |
| **Data Models** | `@dataclass`, `pydantic` | [src/models.py](file:///Users/ashish/Desktop/plausibility_ai/src/models.py) |
| **Indexing** | `PyMuPDF`, `pymupdf4llm`, `ast`, `chromadb` | [src/indexing/pdf_parser.py](file:///Users/ashish/Desktop/plausibility_ai/src/indexing/pdf_parser.py), [src/indexing/code_parser.py](file:///Users/ashish/Desktop/plausibility_ai/src/indexing/code_parser.py), [src/indexing/vector_store.py](file:///Users/ashish/Desktop/plausibility_ai/src/indexing/vector_store.py) |
| **Extraction** | `openpyxl` | [src/extraction/breach_extractor.py](file:///Users/ashish/Desktop/plausibility_ai/src/extraction/breach_extractor.py) |
| **Retrieval** | RAG (ChromaDB cosine sim) | [src/retrieval/rag_retriever.py](file:///Users/ashish/Desktop/plausibility_ai/src/retrieval/rag_retriever.py) |
| **LLM Analysis** | `httpx` (async), `tenacity`, OpenAI API protocol | [src/analysis/llm_client.py](file:///Users/ashish/Desktop/plausibility_ai/src/analysis/llm_client.py), [src/analysis/comment_prompt_builder.py](file:///Users/ashish/Desktop/plausibility_ai/src/analysis/comment_prompt_builder.py), [src/analysis/response_parser.py](file:///Users/ashish/Desktop/plausibility_ai/src/analysis/response_parser.py) |
| **Excel Output** | `openpyxl` styling & data validation | [src/output/excel_annotator.py](file:///Users/ashish/Desktop/plausibility_ai/src/output/excel_annotator.py), [src/output/simple_annotator.py](file:///Users/ashish/Desktop/plausibility_ai/src/output/simple_annotator.py) |

---

## 3. Agent Operational Rules

### Rule 1: Always Inspect Authoritative Code Before Modifying
- Do not infer data structures, dataclass fields, or method signatures from snippets. Inspect full class definitions in `src/models.py` or `src/config.py`.

### Rule 2: Preserve RAG Evidence Chain & Citations
- Any changes to retrieval (`src/retrieval/`) or prompt building (`src/analysis/`) must ensure citations (`chunk.citation_string()`) are preserved and passed to the LLM prompt.

### Rule 3: Error Isolation & Graceful Degradation
- The batch execution pipeline (`cli.py` -> `_analyze_async`) processes multiple breaches concurrently.
- If an individual LLM request or response parsing step fails, do not crash the entire batch. Use `ResponseParser._error_result()` or safe fallback values so remaining breaches complete.

### Rule 4: Excel Integrity & Openpyxl Formatting
- When modifying `ExcelAnnotator`, preserve existing sheet layout, cell formulas, and column widths.
- Ensure severity color coding (`Critical` = Red, `Major` = Orange, `Moderate` = Yellow, `Minor` = Green, `Informational` = Blue) remains consistent.

### Rule 5: Keep Operations Local & Air-Gapped
- Maintain zero external dependency calls unless explicitly requested. Embeddings should run via local sentence-transformers / BAAI model or local OpenAI-compatible endpoint.

---

## 4. Verification Workflow for Agents

When making changes:
1. **Lint/Syntax Check:** Verify imports and code syntax.
2. **Execute Indexing (Dry Run / Test Run):**
   ```bash
   poetry run python -m src.cli --config src/config/config.yaml index
   ```
3. **Run Unit / Integration Tests:**
   ```bash
   poetry run pytest
   ```
