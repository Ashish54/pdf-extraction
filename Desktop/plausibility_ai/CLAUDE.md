# claude.md — Project Guide for Claude

This document serves as an operational guide for AI context, architectural understanding, and engineering guidelines when working on **Plausibility AI**.

---

## 1. Project Overview

**Plausibility AI** is a RAG-powered (Retrieval-Augmented Generation) triage and commentary system for financial risk model plausibility test breaches.

- **Primary Goal:** Automate the initial analysis of model output breaches from Excel reports by retrieving context from model documentation (PDFs) and source code (AST-parsed Python), feeding it to a self-hosted LLM, and generating structured Excel annotations with evidence citations.
- **Security & Privacy:** Uses local/self-hosted LLMs (OpenAI-compatible vLLM endpoints like Llama 3 70B or Qwen models) and local embeddings (`sentence-transformers` / `bge-small-en-v1.5`) to keep sensitive financial model logic on-premises.

---

## 2. Common Development & Execution Commands

### Environment Setup
```bash
python3.14 -m venv .venv
source .venv/bin/activate
poetry install
```

### CLI Commands
- **Index Documentation and Source Code:**
  ```bash
  poetry run python -m src.cli --config src/config/config.yaml index
  ```
- **Analyze an Excel Plausibility Report:**
  ```bash
  poetry run python -m src.cli --config src/config/config.yaml analyze path/to/report.xlsx --output path/to/annotated_output.xlsx
  ```

### Running Tests (pytest)
```bash
poetry run pytest
```

---

## 3. Architecture & Core Pipeline

```
Excel Breach Report 
  └─► BreachExtractor (src/extraction/breach_extractor.py)
       └─► RAGRetriever (src/retrieval/rag_retriever.py) ◄── ChromaDB Vector Store
            └─► PromptBuilder (src/analysis/comment_prompt_builder.py)
                 └─► LLMClient (src/analysis/llm_client.py - vLLM / OpenAI API format)
                      └─► ResponseParser (src/analysis/response_parser.py - Pydantic validation)
                           └─► ExcelAnnotator (src/output/excel_annotator.py)
```

### Directory Structure & Responsibilities
- `src/cli.py`: Click CLI entry point.
- `src/config.py` & `src/config/config.yaml`: Configuration loading and dataclasses.
- `src/models.py`: Data models (`BreachRecord`, `DocumentChunk`, `AnalysisResult`, `Severity`, `Confidence`).
- `src/indexing/`:
  - `pdf_parser.py`: PyMuPDF/pymupdf4llm parsing & chunking.
  - `code_parser.py`: Python AST chunking (function/class level).
  - `vector_store.py`: ChromaDB integration.
  - `embedding_client.py`: SentenceTransformer embedding integration.
  - `metadata_generator.py`: Document metadata extraction.
- `src/extraction/`: `breach_extractor.py` parses Excel sheets for breach rows.
- `src/retrieval/`: `rag_retriever.py` queries ChromaDB for relevant doc & code chunks.
- `src/analysis/`:
  - `llm_client.py`: Async HTTP LLM API calls with `httpx` & `tenacity` retries.
  - `comment_prompt_builder.py`: RAG prompt layout & JSON instructions.
  - `response_parser.py`: JSON parsing & Pydantic validation.
- `src/output/`: `excel_annotator.py` & `simple_annotator.py` write rich formatting and AI columns back into Excel.
- `docs/`: Architectural documentation (`PROJECT_OVERVIEW.md`, `IMPLEMENTATION_PLAN.md`).

---

## 4. Coding Standards & Conventions

1. **Python Version:** 3.14+
2. **Type Annotations & Dataclasses:** Use standard typing (`Optional`, `List`, `Dict`, `Tuple`) and Python `@dataclass` or `pydantic` schemas for domain entity models.
3. **Async / Concurrency:** Use `asyncio` and `httpx.AsyncClient` for LLM calls to enable concurrent batch processing (`analyze_batch`).
4. **Structured LLM Output:** Always enforce JSON schema compliance. Prompt for JSON and validate output using Pydantic models (`AnalysisResult`).
5. **Error Handling & Resilience:**
   - Fall back to standard error results (`parser._error_result`) rather than raising raw exceptions when processing individual breaches.
   - Use `tenacity` for exponential backoff on network/LLM API calls.
6. **Path Resolution:** Always use `pathlib.Path` instead of raw string manipulations.

---

## 5. Key Design Principles

- **Traceable Evidence:** Every AI recommendation MUST include citations from retrieved document/code chunks.
- **Graceful Fallbacks:** If RAG context is missing or low-confidence, flag the item with `Confidence.LOW` and note uncertainties rather than hallucinating details.
- **Human-in-the-Loop:** All outputs are formatted as draft recommendations for SME validation in Excel with approval dropdowns.
