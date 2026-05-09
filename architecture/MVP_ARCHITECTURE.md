# MVP Architecture

This document describes the complete architecture for the factory-rag-assistant MVP. It covers every component, every data flow, every interface contract, and every design constraint. It is the implementation blueprint — before writing a line of code, a developer should be able to read this and know exactly what to build.

---

## High-Level Pipeline

There are two separate pipelines. They share the same vector store but run at different times.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  INGESTION PIPELINE  (run once per document, or on update)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  data/raw/*.pdf
       │
       ▼
  ┌──────────────────────┐
  │  Document Loader     │  LangChain PyPDFLoader
  │  app/ingestion/      │  extracts text + page numbers (0-indexed;
  │  loader.py           │  add 1 in metadata step)
  └──────────┬───────────┘
             │  List[Document(page_content, metadata)]
             ▼
  ┌──────────────────────┐
  │  Text Splitter       │  LangChain RecursiveCharacterTextSplitter
  │  app/ingestion/      │  1500 chars, 200 overlap (≈ 300–400 tokens)
  │  chunker.py          │  preserves page_number, source_file in metadata
  └──────────┬───────────┘
             │  List[Chunk]
             ▼
  ┌──────────────────────┐
  │  Metadata Enricher   │  adds document_type, product_family,
  │  app/ingestion/      │  section_heading (plain-text heuristic),
  │  metadata.py         │  chunk_id, token_count (word count approx)
  └──────────┬───────────┘
             │  List[dict]  ← enriched chunk records
             ▼
  ┌──────────────────────┐
  │  JSONL Writer        │  one file per source doc
  │  app/ingestion/      │  data/processed/<stem>.jsonl
  │  metadata.py         │  inspectable; re-embed without re-parsing
  └──────────┬───────────┘
             │  (separate operation — run embedder after ingestion)
             ▼
  ┌──────────────────────┐
  │  Embedding Model     │  OllamaEmbeddings(model="nomic-embed-text")
  │  app/embeddings/     │  reads from data/processed/ JSONL
  │  embedder.py         │
  └──────────┬───────────┘
             │  List[vector]
             ▼
  ┌──────────────────────┐
  │  Vector Store        │  ChromaDB PersistentClient
  │  app/embeddings/     │  collection: "factory_docs"
  │  store.py            │  hnsw:space = cosine  ← must be explicit
  └──────────────────────┘  stored at: data/embeddings/


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  QUERY PIPELINE  (runs on every user question)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  POST /api/ask
  { query: str, role: str, product_family?: str }
       │
       ▼
  ┌──────────────────────┐
  │  Request Validator   │  Pydantic: validate role against enum,
  │  app/api/schemas.py  │  query non-empty, product_family optional
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │  Retriever           │  embed query with nomic-embed-text,
  │  app/retrieval/      │  cosine similarity search, top_k=5
  │  retriever.py        │  optional metadata filter: product_family
  └──────────┬───────────┘
             │  List[RetrievedChunk(text, score, metadata)]
             ▼
  ┌──────────────────────┐
  │  Prompt Assembler    │  load prompts/system/base.md
  │  app/prompts/        │  + prompts/roles/<role>.md
  │  assembler.py        │  + format context blocks with source labels
  └──────────┬───────────┘
             │  assembled_prompt: str
             ▼
  ┌──────────────────────┐
  │  LLM Provider        │  OllamaProvider → POST localhost:11434
  │  app/llm/            │  model: gemma4:e4b, temp: 0.1, max_tokens: 600
  │  ollama_provider.py  │
  └──────────┬───────────┘
             │  raw_response: str
             ▼
  ┌──────────────────────┐
  │  Response Parser     │  extract citations from [cite: ...] markers,
  │  app/llm/            │  build AnswerResponse schema
  │  parser.py           │
  └──────────┬───────────┘
             │
             ▼
  HTTP 200: AnswerResponse
  {
    answer: str,
    citations: List[Citation],
    role: str,
    model: str,
    chunks_used: int
  }
```

---

## Directory Structure

```
app/
├── api/
│   ├── main.py          # FastAPI app, lifespan, router registration
│   ├── routes.py        # POST /ask, POST /ingest, GET /health
│   └── schemas.py       # Pydantic request/response models
│
├── ingestion/
│   ├── loader.py        # LangChain PyPDFLoader wrapper
│   ├── chunker.py       # RecursiveCharacterTextSplitter wrapper
│   └── metadata.py      # Metadata enrichment: doc_type, product_family, chunk_id, heading heuristic
│
├── embeddings/
│   ├── embedder.py      # OllamaEmbeddings wrapper
│   └── store.py         # ChromaDB client: upsert, query, delete
│
├── retrieval/
│   └── retriever.py     # Query embedding + ChromaDB similarity search + metadata filter
│
├── llm/
│   ├── base.py          # Abstract LLMProvider (generate(prompt) → str)
│   ├── ollama_provider.py  # Ollama implementation
│   └── parser.py        # Citation extraction from model output
│
├── prompts/
│   └── assembler.py     # Load role template, format context blocks, build full prompt
│
└── config.py            # Settings via pydantic-settings: model names, paths, top_k
```

---

## API Contracts

### `POST /api/ask`

**Request**:
```json
{
  "query": "What is the maximum operating temperature of the X200?",
  "role": "rd_engineer",
  "product_family": "X200"
}
```

`role` must be one of: `rd_engineer`, `tech_service`, `sales`, `purchasing`, `production`, `customer_support`

`product_family` is optional. When provided, retrieval is filtered to chunks tagged with that family.

**Response** (`200 OK`):
```json
{
  "answer": "The X200 has a maximum operating temperature of 85°C [cite: X200_datasheet.pdf, p.4, \"4.1 Thermal Specifications\"].",
  "citations": [
    {
      "source_file": "X200_datasheet.pdf",
      "page_number": 4,
      "section_heading": "4.1 Thermal Specifications"
    }
  ],
  "role": "rd_engineer",
  "model": "gemma4:e4b",
  "chunks_used": 3
}
```

**Error responses**:
- `422` — validation error (unknown role, empty query)
- `503` — Ollama not reachable
- `404` — no relevant chunks found (returns `answer: null`, `no_results: true`)

---

### `POST /api/ingest`

Triggers ingestion of all PDFs in `data/raw/` (or a specified subfolder). Returns a summary.

**Request** (optional body):
```json
{
  "path": "data/raw/manuals/",
  "document_type": "manual",
  "product_family": "X200"
}
```

**Response**:
```json
{
  "files_processed": 3,
  "chunks_created": 847,
  "chunks_upserted": 847,
  "errors": []
}
```

---

### `GET /api/health`

Returns service status and whether Ollama is reachable.

```json
{
  "status": "ok",
  "ollama": "reachable",
  "vector_store": "ok",
  "chunks_indexed": 847
}
```

---

## Data Models (Pydantic)

```python
# app/api/schemas.py

class Role(str, Enum):
    rd_engineer = "rd_engineer"
    tech_service = "tech_service"
    sales = "sales"
    purchasing = "purchasing"
    production = "production"
    customer_support = "customer_support"

class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    role: Role
    product_family: Optional[str] = None

class Citation(BaseModel):
    source_file: str
    page_number: int
    section_heading: str

class AskResponse(BaseModel):
    answer: Optional[str]
    citations: List[Citation]
    role: str
    model: str
    chunks_used: int
    no_results: bool = False

class IngestRequest(BaseModel):
    path: str = "data/raw/"
    document_type: Optional[str] = None
    product_family: Optional[str] = None

class IngestResponse(BaseModel):
    files_processed: int
    chunks_created: int
    chunks_upserted: int
    errors: List[str]
```

---

## Configuration

All runtime configuration lives in `app/config.py` using `pydantic-settings`. Values come from environment variables (`.env` file) with defaults that work out of the box for local development.

```python
class Settings(BaseSettings):
    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "gemma4:e4b"
    embedding_model: str = "nomic-embed-text"

    # Retrieval
    top_k: int = 5
    max_context_tokens: int = 3000

    # Paths
    raw_docs_path: str = "data/raw/"
    embeddings_path: str = "data/embeddings/"
    processed_path: str = "data/processed/"

    # LLM generation
    llm_temperature: float = 0.1
    llm_max_tokens: int = 600

    class Config:
        env_file = ".env"
```

No hardcoded values anywhere else in the codebase. All modules import `settings` from `app/config.py`.

---

## LangChain Usage Boundary

LangChain is used **only** in these files:

| File | LangChain component used |
|------|--------------------------|
| `app/ingestion/loader.py` | `PyPDFLoader` |
| `app/ingestion/chunker.py` | `RecursiveCharacterTextSplitter` |
| `app/embeddings/embedder.py` | `OllamaEmbeddings` |
| `app/embeddings/store.py` | `Chroma` (LangChain's ChromaDB wrapper) |

LangChain is **not** used for:
- Chains (`RetrievalQA`, `LLMChain`, etc.)
- Agents or tools
- Prompt templates (we use raw `.md` files loaded at runtime)
- LLM calls (we call Ollama directly through our own provider)

This boundary is intentional. If LangChain is found outside these four files, it is a scope violation.

---

## Chunking Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Chunk size | 1500 characters | ≈ 300–400 tokens for English technical text; within nomic-embed-text's 512-token limit |
| Overlap | 200 characters | ≈ 13% overlap; preserves sentence context across boundaries |
| Splitter | `RecursiveCharacterTextSplitter` | Respects paragraph → sentence → word boundaries in that order |
| Separators | `["\n\n", "\n", ". ", " "]` | Matches PDF structure (double-newline = paragraph break) |

**Units are characters, not tokens.** `RecursiveCharacterTextSplitter.chunk_size` is always in characters. The token estimate assumes average English word length. Phase 3 evaluation will test 1000 and 2000 character variants.

---

## Memory Budget (16GB RAM)

At query time with all components loaded:

| Component | RAM |
|-----------|-----|
| macOS + background apps | ~4.0 GB |
| Python process (FastAPI + LangChain + ChromaDB) | ~0.8 GB |
| nomic-embed-text (Ollama, loaded) | ~0.5 GB |
| gemma4:e4b (Ollama) | ~3.5 GB |
| ChromaDB (index in memory, ~50k chunks) | ~0.5 GB |
| **Total** | **~9.3 GB** |
| **Headroom** | **~6.7 GB** |

This is a comfortable fit. Using Gemma 4 12B would consume approximately 7–8GB for the model alone, leaving only ~3.5GB headroom — marginal for a developer machine.

---

## What Is Explicitly Out of MVP Scope

| Feature | When |
|---------|------|
| Web UI (Next.js) | Phase 2 |
| Auth / role identity from session | Phase 4 |
| Reranking (cross-encoder) | Phase 3 |
| Conversation history / multi-turn | Phase 2+ |
| Document upload via API (multipart) | Phase 2 |
| Cloud LLM fallback | Phase 4 |
| Evaluation harness | Phase 3 |
| Docker / containerisation | Phase 4 |

The MVP ingest endpoint accepts a server-side path, not a file upload. Documents are placed in `data/raw/` manually for MVP.

---

## Failure Modes and Handling

| Failure | Detection | Handling |
|---------|-----------|---------|
| Ollama not running | Health check on startup | `GET /health` returns `ollama: unreachable`; `POST /ask` returns `503` |
| No chunks retrieved | Empty result from ChromaDB | Return `no_results: true`, skip LLM call |
| LLM returns no citations | Parse step finds zero `[cite: ...]` markers | Re-prompt once with explicit citation instruction; if still none, extract citations from context blocks used |
| PDF has no text layer (scanned) | Empty `page_content` from PyPDFLoader | Skip file, add to `errors` in ingest response, log warning |
| Chunk exceeds token limit | `token_count > 600` after splitting | Log error with chunk ID; do not upsert; report in ingest response |

---

## Testing Approach (MVP)

No full test suite in Phase 1. Two lightweight checks:

1. **`scripts/smoke_test.py`** — ingests one test PDF, runs one query, asserts the response has `answer` and at least one `citation`. Runnable in under 30 seconds.

2. **`GET /health`** — structural health check verifiable with `curl localhost:8000/api/health`.

Formal evaluation begins in Phase 3 with `evals/`.
