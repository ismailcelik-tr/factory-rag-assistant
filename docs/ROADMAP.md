# ROADMAP.md

The project roadmap broken into four phases. Each phase has a clear definition of done, a set of deliverables, and explicit out-of-scope items. Phases are sequential — Phase 2 does not start until Phase 1 is complete and tested.

---

## Phase 1 — Working MVP

**Goal**: A single user can place PDFs in `data/raw/`, run ingestion, and ask role-tagged questions via a REST API. Every answer has at least one citation.

**Definition of done**: `scripts/smoke_test.py` passes end-to-end on a real factory document.

### Deliverables

**Ingestion pipeline** (`app/ingestion/`)
- `loader.py` — PyPDFLoader wrapper, returns LangChain `Document` list with page numbers
- `chunker.py` — RecursiveCharacterTextSplitter, 512-token target, 64-token overlap
- `metadata.py` — enriches chunks with `document_type`, `product_family`, `section_heading` (heuristic), `chunk_id`

**Embedding + storage** (`app/embeddings/`)
- `embedder.py` — OllamaEmbeddings with nomic-embed-text
- `store.py` — ChromaDB persistent client, collection management, upsert, similarity query

**Retrieval** (`app/retrieval/`)
- `retriever.py` — embeds query, runs cosine similarity search, returns top-5 chunks with scores and metadata, optional `product_family` filter

**LLM layer** (`app/llm/`)
- `base.py` — abstract `LLMProvider` with single method `generate(prompt: str) → str`
- `ollama_provider.py` — calls `localhost:11434`, passes temperature and max_tokens from config
- `parser.py` — extracts `[cite: ...]` markers from model output into `Citation` objects

**Prompt assembly** (`app/prompts/`)
- `assembler.py` — loads `prompts/system/base.md` + `prompts/roles/<role>.md`, formats context blocks with source labels, builds final prompt string

**API** (`app/api/`)
- `schemas.py` — Pydantic models: `AskRequest`, `AskResponse`, `IngestRequest`, `IngestResponse`, `Citation`
- `routes.py` — `POST /api/ask`, `POST /api/ingest`, `GET /api/health`
- `main.py` — FastAPI app, lifespan (startup health check), router registration

**Configuration**
- `app/config.py` — pydantic-settings, all values from `.env`, local defaults that work without any `.env`
- `.env.example` — documented template

**Scripts**
- `scripts/ingest.py` — CLI wrapper for `POST /api/ingest` or direct pipeline call
- `scripts/chat.py` — interactive CLI loop: prompt for question, prompt for role, print answer + citations
- `scripts/smoke_test.py` — automated end-to-end check

**Project setup**
- `pyproject.toml` — pinned dependencies, dev extras
- `docs/setup.md` — complete setup instructions (updated from placeholder)

### Out of scope in Phase 1
- Web UI
- File upload via HTTP
- Conversation history
- Evaluation harness (just smoke test)
- Auth of any kind
- Docker

---

## Phase 2 — Role Routing + API Hardening

**Goal**: All six role prompts produce demonstrably different answers for the same question. The API is stable enough to build a UI against.

**Definition of done**: Side-by-side comparison of the same query answered under all six roles shows clearly differentiated tone and emphasis.

### Deliverables

- All six role prompt templates validated against real documents (currently written, to be tested)
- API versioning: `/api/v1/ask` — breaking change safety for future UI
- `POST /api/v1/ask` with conversation `session_id` support (stateless on server side — client holds history)
- `GET /api/v1/roles` — returns valid role list (lets the future UI populate a dropdown dynamically)
- Error response schema standardised: `{error: str, code: str}` for all 4xx/5xx
- Structured logging: every request logs `query_hash`, `role`, `chunks_retrieved`, `response_time_ms`
- `docs/API.md` — full API reference with examples

### Out of scope in Phase 2
- Web UI (defined for Phase 2 in the original plan, but pushing it: a stable tested API first is worth the delay)
- Reranking
- Evaluation harness

---

## Phase 3 — Quality and Evaluation

**Goal**: Retrieval quality and answer quality are measured with real numbers against a ground-truth dataset. Any tuning decision is backed by a before/after eval comparison.

**Definition of done**: Eval suite runs in CI; hit rate @ 5 ≥ 0.80 on `full_suite.jsonl`.

### Deliverables

- `evals/datasets/full_suite.jsonl` — 50+ hand-authored QA pairs from real ingested documents, covering all six roles
- `evals/datasets/role_coverage.jsonl` — at least 5 questions per role
- `evals/run_evals.py` — runnable evaluation script
- Retrieval metrics: hit rate @ 5, MRR
- Answer metrics: citation accuracy, semantic similarity to reference answers
- `evals/results/` — at least one baseline run committed as a benchmark
- Reranking experiment: cross-encoder reranker on top of retrieval, measured against baseline
- Chunking experiment: compare 256 / 512 / 768 token sizes on the eval set
- Phase 3 findings documented in a new ADR if any parameter change is adopted

### Out of scope in Phase 3
- Web UI
- Auth
- Mobile API

---

## Phase 4 — Extension

**Goal**: The system is demonstrably extendable to a production-adjacent deployment. At least one extension is implemented and tested.

**Target extensions** (implement at least two):

**Web UI**
- Next.js chat interface
- Role selector dropdown (populated from `GET /api/v1/roles`)
- Citation cards linking to source document and page
- Conversation history (client-side, sent in request body)

**Cloud LLM fallback**
- `ClaudeProvider` implementation in `app/llm/`
- Config flag to switch providers without code change
- Eval comparison: Gemma 4 vs Claude on `full_suite.jsonl`

**Document upload via API**
- `POST /api/v1/documents` — multipart file upload
- Server-side ingestion triggered automatically
- Status endpoint: `GET /api/v1/documents/{id}/status`

**Auth and role identity from session**
- JWT-based auth (or Clerk integration for Next.js)
- Role inferred from user profile, not passed in request body
- Role can be overridden by admin users

**Mobile API layer**
- No new endpoints needed — Phase 1/2 API is already mobile-compatible
- This deliverable is documentation: OpenAPI spec export, mobile client example (Swift or Kotlin)

---

## Cross-Phase Principles

These apply throughout all phases:

- **No phase starts before its predecessor's definition of done is met.** Do not start Phase 2 UI work while Phase 1 retrieval is broken.
- **Every architectural change gets an ADR.** See `architecture/decisions/TEMPLATE.md`.
- **Eval numbers back every tuning claim.** "I improved retrieval" is not a claim without a before/after metric.
- **`data/processed/` and `data/embeddings/` are never committed.** They are generated artefacts.
- **LangChain stays within its defined boundary.** See `docs/TECH_STACK_DECISION.md`.

---

## Current Status

| Phase | Status |
|-------|--------|
| Phase 1 | In progress — repository and documentation complete, application code not yet written |
| Phase 2 | Not started |
| Phase 3 | Not started |
| Phase 4 | Not started |
