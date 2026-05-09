# SESSION_CONTEXT.md

Implementation state snapshot for session continuation.
**Do not re-plan architecture. Pick up at Step 4.**

---

## Phase and Progress

**Phase 1 — Working MVP** (10 steps total)

| Step | Description | Status |
|------|-------------|--------|
| 1 | Project scaffolding | ✅ Done |
| 2 | Ingestion pipeline (loader + chunker + metadata) | ✅ Done |
| 3 | Write processed JSONL (`save_chunks`) | ✅ Done |
| 4 | Embeddings and vector store | ⬜ **Next** |
| 5 | Retrieval | ⬜ |
| 6 | LLM provider | ⬜ |
| 7 | Prompt assembler | ⬜ |
| 8 | Pydantic schemas | ⬜ |
| 9 | FastAPI application | ⬜ |
| 10 | CLI scripts | ⬜ |

---

## Files Created / Updated (Sessions 1–3)

### Step 1
- `pyproject.toml`
- `.env.example`
- `app/__init__.py`, `app/api/__init__.py`, `app/ingestion/__init__.py`
- `app/embeddings/__init__.py`, `app/retrieval/__init__.py`, `app/llm/__init__.py`
- `app/prompts/__init__.py`, `app/tests/__init__.py`
- `app/config.py`

### Step 2
- `app/ingestion/loader.py` — `load_pdf()`, `load_directory()`
- `app/ingestion/chunker.py` — `split_documents()`
- `app/ingestion/metadata.py` — `enrich()`, `_detect_heading()`, `_infer_document_type()`, `_validate_and_log()`
- `app/tests/test_ingestion.py` — 41 tests (all passing)

### Step 3
- `app/ingestion/metadata.py` — added `save_chunks(chunks, output_path) -> Path`
- `app/tests/test_ingestion.py` — added `TestSaveChunks` (8 tests)

### Documentation / Architecture (Session 1)
- `CLAUDE.md`, `PROJECT_CONTEXT.md`, `AGENTS.md`, `architecture/MVP_ARCHITECTURE.md`
- `architecture/overview.md`, `architecture/decisions/` (ADRs)
- `docs/OPEN_DECISIONS.md` (all 12 resolved), `docs/IMPLEMENTATION_PLAN.md`
- `docs/ROADMAP.md`, `docs/TECH_STACK_DECISION.md`, `docs/setup.md`
- `prompts/system/base.md`
- `prompts/roles/rd_engineer.md`, `tech_service.md`, `sales.md`, `purchasing.md`, `production.md`, `customer_support.md`
- `agents/`, `skills/` directories

---

## Test Status

```
pytest app/tests/test_ingestion.py -v   →   49 passed in 0.05s
ruff check app/ingestion/ app/tests/   →   All checks passed
```

No other test files exist yet.

---

## Environment Setup

```bash
# Python venv (created in session 1)
source .venv/bin/activate

# Install (already done; re-run if deps change)
pip install -e ".[dev]"

# Start Ollama (must be running before any pipeline step)
ollama serve

# Required models (one-time pull)
ollama pull gemma4:e4b
ollama pull nomic-embed-text
```

### Verification commands

```bash
# Config loads correctly
python -c "from app.config import settings; print(settings.llm_model)"

# Tests
python -m pytest app/tests/ -v

# Lint
ruff check app/ scripts/ evals/
```

---

## Locked Architecture Decisions (do not re-open)

| Decision | Value |
|----------|-------|
| LLM | `gemma4:e4b` via Ollama |
| Embedding model | `nomic-embed-text` via Ollama |
| Vector store | ChromaDB with `{"hnsw:space": "cosine"}` — set at collection creation, cannot change |
| Chunking | 1500 chars / 200 overlap (characters, not tokens) |
| Separators | `["\n\n", "\n", ". ", " "]` |
| Pipeline | Two-stage: JSONL → ChromaDB |
| Ollama call | `/api/chat`, `stream: false`, `timeout: 120s` |
| Prompt structure | system = base.md + role template; user = context blocks + question |
| Page indexing | PyPDFLoader is 0-indexed → `+1` in `enrich()` |
| Product family | Full path stored in ChromaDB; basename in API response |
| Config | `app/config.py` only; pydantic-settings v2; `model_config = {"env_file": ".env"}` |
| Build backend | `setuptools.build_meta` (NOT `setuptools.backends.legacy:build` — fails) |
| Dependency pins | `>=x.y` lower bounds (Python 3.14.4 has no pre-built wheels for `==x.y.*` pins) |

---

## Key Package Import Paths

```python
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma        # wrapper only (store.py uses chromadb directly)
import chromadb                            # PersistentClient used directly
```

Do not import from the bare `langchain` package — components live in the sub-packages above.

---

## Data Directories

```
data/raw/        ← place PDFs here; never write here (read-only)
data/processed/  ← JSONL output from save_chunks(); NOT committed
data/embeddings/ ← ChromaDB artefacts; NOT committed
```

Both `data/processed/` and `data/embeddings/` are in `.gitignore`.

---

## Known Issues / Risks

- **No sample PDF in `data/raw/`** yet — smoke test (`scripts/smoke_test.py`) will fail until at least one PDF is placed there. Step 4 verification also requires a PDF.
- **Ollama must be running** before any embedding or LLM call. Embedder and provider will fail with a connection error if not started.
- **ChromaDB cosine metric** is set at collection creation. If the collection already exists from a previous run with a different metric, drop it first (`client.delete_collection(name)`) before recreating.
- **`app/tests/` has no test for `loader.py`** — intentional; PyPDFLoader requires a real PDF file. Manual verification only.

---

## Next Step: Step 4 — Embeddings and Vector Store

Implement two files. Follow `docs/IMPLEMENTATION_PLAN.md` Step 4 exactly.

### `app/embeddings/store.py`

```python
import chromadb
from app.config import settings

client = chromadb.PersistentClient(path=settings.embeddings_path)
collection = client.get_or_create_collection(
    name=settings.collection_name,
    metadata={"hnsw:space": "cosine"},  # must be set at creation — cannot change later
)
```

Three functions:
- `upsert_chunks(chunks: list[dict], embeddings: list[list[float]])` — ids from `chunk["chunk_id"]`, documents from `chunk["text"]`, metadatas: `source_file`, `page_number`, `section_heading`, `document_type`, `product_family`
- `query(embedding: list[float], top_k: int, filter: dict = None) -> list[dict]` — returns list of dicts with `text`, `score`, and all metadata; `filter` maps to ChromaDB `where` clause
- Module-level `client` and `collection` instances (created once on import)

### `app/embeddings/embedder.py`

```python
from langchain_ollama import OllamaEmbeddings
from app.config import settings

embeddings_model = OllamaEmbeddings(
    model=settings.embedding_model,
    base_url=settings.ollama_base_url,
)
```

One function: `embed_texts(texts: list[str]) -> list[list[float]]`

### Verification

```bash
# Embed 3 test strings, check vector length == 768, upsert, query
python -c "
from app.embeddings.embedder import embed_texts
vecs = embed_texts(['hello world', 'motor calibration', 'safety warnings'])
print('Vector length:', len(vecs[0]))  # should be 768
"
```

Then upsert those vectors and query with one of the same strings — it must return as the top result.

### Tests to write

Add `app/tests/test_embeddings.py` with integration tests that **require Ollama to be running** — mark them with `pytest.mark.integration` or guard with a `skipif` on Ollama availability. Unit tests (mocking the embeddings model) are acceptable if integration tests are also included.

---

## What the Next Session Must NOT Do

- Do not re-open or re-discuss any resolved decision in `docs/OPEN_DECISIONS.md`
- Do not change chunking parameters (1500/200 chars)
- Do not switch to token-based chunking
- Do not add LangChain chains or agents — use LangChain only for the four components listed above
- Do not add Docker, authentication, or Next.js frontend — Phase 2+ concerns
- Do not add retry logic, fallbacks, or error handling for hypothetical scenarios
- Do not change the `save_chunks` function signature — `scripts/ingest.py` will call it directly
- Do not commit `data/processed/` or `data/embeddings/` directories
