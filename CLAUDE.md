# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment

```bash
# Activate conda environment
source ~/miniforge3/etc/profile.d/conda.sh && conda activate chat_bot

# Run backend (from project root)
PYTHONPATH=src uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Run frontend (separate terminal)
cd docs && python -m http.server 8001

# Run all tests
PYTHONPATH=src pytest tests/ -v

# Run a single test file
PYTHONPATH=src pytest tests/test_main.py -v

# Run a single test
PYTHONPATH=src pytest tests/test_main.py::TestClassName::test_method -v

# Integration tests (require GOOGLE_API_KEY)
PYTHONPATH=src pytest tests/ -v -m integration
```

Required env vars: `GOOGLE_API_KEY`, `UPSTASH_VECTOR_REST_URL`, `UPSTASH_VECTOR_REST_TOKEN`, `PYTHONPATH=src`.

## Architecture

RAG-based chatbot system: crawl websites → chunk & index into vector DB → answer questions via LLM with retrieved context.

**Backend** (`src/`): FastAPI app deployed on Google Cloud Run.
- `main.py` — All HTTP endpoints. Streaming endpoints use SSE (`StreamingResponse`).
- `QA_pipeline.py` — RAG chain using Upstash Vector retriever + Gemini LLM with 8-model fallback on rate limits.
- `mycrawler.py` — Polite web crawler respecting robots.txt and Crawl-Delay. Thread-safe concurrent crawling.
- `indexer.py` — Content extraction via Crawl4AI (Playwright), recursive text splitting, MD5 deduplication at URL and chunk level. Upstash Vector storage with namespace isolation.
- `widget_customizer.py` — `PromptGuard` (input sanitization), `ThemeExtractor` (CSS color parsing from URLs), `WidgetConfigGenerator` (Gemini → JSON config), `WidgetCodeRenderer` (config → self-contained IIFE widget script).

**Frontend** (`docs/`): Vanilla JS with ES6 modules, no build step.
- `index.html` — Management UI (crawl, index, widget customizer sections). Points to production API.
- `local_setup.html` — Identical to `index.html` except `API_BASE` points to `http://localhost:8000`. **Any change to `index.html` must be mirrored in `local_setup.html`.**
- `widget-loader.js` — Embeddable chat widget (floating button, markdown rendering via marked.js + DOMPurify).
- `crawl.js`, `index.js`, `widget-customizer.js` — ES6 module classes imported as `type="module"`.

**Namespace isolation**: Each chatbot instance uses a separate namespace in Upstash Vector, enabling multi-tenant deployment from a single service.

## Key Patterns

**SSE streaming**: All long-running operations (crawl, index, widget generation) stream progress via SSE. Backend yields `data: {json}\n\n`, frontend reads via `ReadableStream`. Never use blocking endpoints for these operations.

**Widget code generation**: Uses a structured config approach — Gemini produces a JSON `WidgetConfig`, then `WidgetCodeRenderer` templates it into code. This prevents injection bugs vs. having the LLM write raw code.

**Model fallback**: `QA_pipeline.py` cycles through 8 Gemini models on rate limit errors. The order is defined in `llm_models` list.

**Dark theme colors**: Background `#0f1029`, surface `#1a1b2e`, text `#e2e4f0`, accent gradient `#667eea` → `#764ba2`, border `#2e3055`.

## Testing Conventions

- Use `with patch(...)` inside test methods, not `@patch` decorators — decorators trigger imports before `setup_method` runs, causing failures.
- Integration tests requiring external APIs are marked with `@pytest.mark.integration`.
- Cloud logging outputs JSON only (no pretty-print) for Google Cloud Logging compatibility.

## Documentation

- When a significant new feature or functionality is added, update `README.md` to reflect it (e.g., new sections, updated feature lists, usage instructions).

## Deployment

Docker image uses `mcr.microsoft.com/playwright/python:v1.57.0-jammy` base (Playwright pre-installed). CI/CD via GitHub Actions (`.github/workflows/deploy.yml`): test → build → deploy to Cloud Run on port 8080.
