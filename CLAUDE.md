# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Identity

`factory-rag-assistant` is a RAG system for factory document knowledge. It ingests technical documents, embeds them, and answers role-specific questions with citations. The LLM is Gemma 4 via Ollama by default. See `PROJECT_CONTEXT.md` for the full design rationale and `AGENTS.md` for subagent definitions.

---

## Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Start Ollama (must be running before any pipeline step)
ollama serve

# Pull required models (one-time setup)
ollama pull gemma4:e4b
ollama pull nomic-embed-text

# Run the API server
uvicorn app.api.main:app --reload

# Ingest documents from data/raw/
python scripts/ingest.py

# Interactive CLI query
python scripts/chat.py --role tech_service

# Smoke test (end-to-end: ingest one doc, ask one question)
python scripts/smoke_test.py

# Run evaluations (Phase 3)
python evals/run_evals.py --dataset evals/datasets/smoke_test.jsonl --mode full

# Run tests
pytest app/tests/ -v

# Run a single test
pytest app/tests/test_retrieval.py::test_top_k_returns_five -v

# Lint
ruff check app/ scripts/ evals/
```

> Commands that reference files not yet created are the next implementation target. See `docs/ROADMAP.md` Phase 1.

---

## Repository Map

| Path | What lives here |
|------|----------------|
| `app/api/` | FastAPI app, routes (`/ask`, `/ingest`, `/health`), Pydantic schemas |
| `app/ingestion/` | `loader.py` (PyPDFLoader), `chunker.py` (RecursiveCharacterTextSplitter), `metadata.py` |
| `app/embeddings/` | `embedder.py` (OllamaEmbeddings / nomic-embed-text), `store.py` (ChromaDB) |
| `app/retrieval/` | `retriever.py` — cosine similarity search, metadata filter |
| `app/llm/` | `base.py` (abstract provider), `ollama_provider.py`, `parser.py` (citation extraction) |
| `app/prompts/` | `assembler.py` — loads role templates, formats context blocks |
| `app/config.py` | pydantic-settings: all config from `.env` |
| `prompts/system/` | `base.md` — universal rules for every LLM call |
| `prompts/roles/` | One `.md` per role — persona, emphasis, length constraints |
| `agents/` | Claude Code subagent definitions (see `AGENTS.md`) |
| `skills/` | Reusable Claude Code skill definitions |
| `data/raw/` | Original factory documents — never modified |
| `data/processed/` | Generated JSONL — not committed |
| `data/embeddings/` | ChromaDB artefacts — not committed |
| `evals/` | Ground-truth QA datasets and evaluation harness |
| `architecture/` | `overview.md`, `MVP_ARCHITECTURE.md`, `decisions/` (ADRs) |
| `docs/` | `setup.md`, `ROADMAP.md`, `TECH_STACK_DECISION.md` |
| `scripts/` | `ingest.py`, `chat.py`, `smoke_test.py` |

---

## Key Architectural Rules

1. **LLM calls only go through `app/llm/`**. Never call Ollama or any cloud LLM API directly from retrieval, ingestion, or API layers.

2. **Role is always explicit**. Every call through the RAG pipeline that touches prompts must carry a `role` parameter. No defaulting to a generic prompt silently.

3. **Citations are mandatory**. The `answer-agent` and any answer-generation code must return a `citations` field. An answer without citations is a bug.

4. **`data/raw/` is read-only**. Ingestion scripts read from it but never write to it. Factory documents are source of truth.

5. **Eval before optimise**. Any change to chunk size, embedding model, top-k, or prompt templates must be validated against `evals/` before being merged. Run `eval-agent` first.

6. **ADR for architectural changes**. Any change that affects the overall data flow, LLM interface, vector store, or chunking strategy requires an ADR in `architecture/decisions/`. Copy the template from `architecture/decisions/TEMPLATE.md`.

---

## Agent and Skill Workflow

Use the agents defined in `AGENTS.md` for multi-step pipeline tasks. Use skills in `skills/` for reusable single-concern operations. For a full pipeline run:

1. `ingestion-agent` — process new docs
2. `embedding-agent` — index them
3. `retrieval-agent` + `answer-agent` — answer a query
4. `eval-agent` — measure quality

---

## LLM Configuration

The default model is **`gemma4:e4b` via Ollama**. Ensure Ollama is running locally (`ollama serve`) and the model is pulled (`ollama pull gemma4:e4b`). All provider configuration lives in `app/config.py`. Do not hardcode model names outside that file.

---

## What Not to Do

- Do not commit anything under `data/processed/` or `data/embeddings/` — these are generated artefacts.
- Do not commit `.env` files or any file containing API keys.
- Do not add retry logic, fallbacks, or error handling for scenarios that haven't been observed in practice.
- Do not add comments that describe what the code does — only why, when the reason is non-obvious.
