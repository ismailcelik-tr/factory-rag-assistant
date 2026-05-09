# IMPLEMENTATION_PLAN.md

A step-by-step build order for Phase 1 (Working MVP). Written for a single developer on a 16GB MacBook. Each step is self-contained and testable before moving to the next.

Resolve all items in `docs/OPEN_DECISIONS.md` before starting Step 1.

---

## Before You Write Any Code

1. Run `ollama pull gemma4` — if it fails, find the correct tag with `ollama list` and update `app/config.py` default accordingly
2. Run `ollama pull nomic-embed-text`
3. Confirm both models appear in `ollama list`
4. Place at least one real factory PDF (or a minimal sample) in `data/raw/samples/` — you need this for the smoke test

---

## Build Order

### Step 1 — Project scaffolding

**What**: Create `pyproject.toml`, all `__init__.py` files, `.env.example`, and `app/config.py`. Nothing else.

**Files to create**:
- `pyproject.toml`
- `.env.example`
- `app/__init__.py`
- `app/api/__init__.py`
- `app/ingestion/__init__.py`
- `app/embeddings/__init__.py`
- `app/retrieval/__init__.py`
- `app/llm/__init__.py`
- `app/prompts/__init__.py`
- `app/config.py`

**`app/config.py`** must contain `Settings` using `pydantic-settings`. Defaults must work without any `.env` file:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "gemma4"          # verify tag before hardcoding
    embedding_model: str = "nomic-embed-text"
    top_k: int = 5
    max_context_tokens: int = 3000
    llm_temperature: float = 0.1
    llm_max_tokens: int = 600
    raw_docs_path: str = "data/raw/"
    embeddings_path: str = "data/embeddings/"
    processed_path: str = "data/processed/"
    collection_name: str = "factory_docs"

    class Config:
        env_file = ".env"

settings = Settings()
```

**Verify**: `pip install -e ".[dev]"` runs without error. `python -c "from app.config import settings; print(settings.llm_model)"` prints the model name.

---

### Step 2 — Document ingestion: loader + chunker + metadata

**What**: Implement the three files in `app/ingestion/`. At the end of this step you can turn a PDF into a JSONL file of chunks.

**Build in this order** (each depends on the previous):

#### `app/ingestion/loader.py`

Wraps `PyPDFLoader`. Returns a list of LangChain `Document` objects with `page_content` and `metadata` (must include `source` and `page`).

One function: `load_pdf(path: str) -> list[Document]`

Also add a utility: `load_directory(path: str) -> list[Document]` — loads all `.pdf` files in a directory recursively.

**Verify**: Load your sample PDF, print the number of pages and first 200 characters of page 1.

#### `app/ingestion/chunker.py`

Wraps `RecursiveCharacterTextSplitter`. Chunk size: **1500 characters**, overlap: **200 characters** (approximately 300–400 tokens for English text — within nomic-embed-text's context window).

```python
# Note: chunk_size and chunk_overlap are in characters, not tokens.
# 1500 chars ≈ 300–400 tokens for English technical text.
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " "],
)
```

One function: `split_documents(documents: list[Document]) -> list[Document]`

Metadata (`source`, `page`) must be preserved on each output chunk. `RecursiveCharacterTextSplitter.split_documents()` does this automatically.

**Verify**: Split your sample PDF. Print total chunk count and average `len(chunk.page_content)`. Should be 1000–1500 chars per chunk.

#### `app/ingestion/metadata.py`

Enriches chunks with computed fields. One function: `enrich(chunks: list[Document], document_type: str = None, product_family: str = None) -> list[dict]`

Returns a list of dicts (not Documents), each with:

| Field | Source | Notes |
|---|---|---|
| `chunk_id` | computed | `<doc_type>_<product_family>_p<page>_<seq>` — use `unknown` if product_family not provided |
| `text` | `chunk.page_content` | |
| `source_file` | `chunk.metadata["source"]` | Full relative path — basename used in citations |
| `page_number` | `chunk.metadata["page"]` | PyPDFLoader uses 0-indexed pages; add 1 to make 1-indexed |
| `section_heading` | heuristic (see below) | `"[No Heading]"` if not found |
| `document_type` | parameter or filename heuristic | `"unknown"` if not determinable |
| `product_family` | parameter | `"unknown"` if not provided |
| `token_count` | `len(text.split())` | Word count as a token approximation — sufficient for validation |

**Heading heuristic** (plain-text only — `PyPDFLoader` gives no font data): scan the chunk text for lines that match any of these patterns at the start of the chunk, before the first sentence:
- All-uppercase line shorter than 60 characters
- Line matching `r"^\d+(\.\d+)*\s+[A-Z]"` (e.g., `"3.2 Motor Calibration"`)
- Line matching `r"^(Section|Chapter|Part)\s+\d"` (case-insensitive)
- If none found, carry the last-known heading across chunks from the same page (pass a `current_heading` accumulator)

**Validate**: No chunk has `token_count > 600`. Every chunk has a non-empty `section_heading`. Log a summary: file name, total chunks, document_type, product_family.

---

### Step 3 — Write processed JSONL

**What**: Add a `save_chunks(chunks: list[dict], output_path: str)` utility — writes the enriched chunks from Step 2 to `data/processed/<source_stem>.jsonl`. One file per source document.

This can live in `app/ingestion/metadata.py` or as a short function in `scripts/ingest.py` — either is fine.

**Verify**: After running the loader → chunker → metadata pipeline on your sample PDF, confirm a readable `.jsonl` file exists in `data/processed/` and each line is valid JSON with all expected fields.

---

### Step 4 — Embeddings and vector store

**What**: Implement `app/embeddings/embedder.py` and `app/embeddings/store.py`. At the end of this step you can take the JSONL from Step 3 and have it indexed in ChromaDB.

#### `app/embeddings/store.py`

ChromaDB persistent client. Three responsibilities:

**Collection setup**:
```python
import chromadb

client = chromadb.PersistentClient(path=settings.embeddings_path)
collection = client.get_or_create_collection(
    name=settings.collection_name,
    metadata={"hnsw:space": "cosine"},   # must be set at creation time
)
```

**Upsert**: `upsert_chunks(chunks: list[dict], embeddings: list[list[float]])`
- `ids`: use `chunk["chunk_id"]`
- `documents`: use `chunk["text"]`
- `embeddings`: the vectors from the embedder
- `metadatas`: dict with `source_file`, `page_number`, `section_heading`, `document_type`, `product_family`

**Query**: `query(embedding: list[float], top_k: int, filter: dict = None) -> list[dict]`
- Returns list of dicts with `text`, `score`, and all metadata fields
- `filter` maps to ChromaDB's `where` clause — used for `product_family` filtering

#### `app/embeddings/embedder.py`

Wraps `OllamaEmbeddings`. One function: `embed_texts(texts: list[str]) -> list[list[float]]`

```python
from langchain_ollama import OllamaEmbeddings

embeddings_model = OllamaEmbeddings(
    model=settings.embedding_model,
    base_url=settings.ollama_base_url,
)
```

Embed in batches (ChromaDB upsert handles batching, but the Ollama embeddings call can be done in one list — test whether this is fast enough before adding manual batching).

**Verify**: Embed 3 test strings. Print the length of each embedding vector (should be 768 for nomic-embed-text). Upsert them. Query with one of the same strings and verify it returns as the top result.

---

### Step 5 — Retrieval

**What**: Implement `app/retrieval/retriever.py`. One function that takes a query string and returns the top-k chunks.

```python
def retrieve(
    query: str,
    top_k: int = settings.top_k,
    product_family: str = None,
) -> list[dict]:
```

Steps inside:
1. Embed `query` using `embedder.embed_texts([query])[0]`
2. Build `filter = {"product_family": product_family}` if product_family is provided, else `None`
3. Call `store.query(embedding, top_k, filter)`
4. Return list of dicts: `[{text, score, source_file, page_number, section_heading}]`

**Verify**: Ingest your sample PDF (Steps 2–4), then retrieve 3 questions you expect to find answers to. Inspect the returned chunks and scores manually. This is your first real quality check — if retrieval looks wrong, debug before moving to LLM integration.

---

### Step 6 — LLM provider

**What**: Implement the three files in `app/llm/`. At the end of this step you can call Gemma and get a text response.

#### `app/llm/base.py`

```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_message: str) -> str:
        ...
```

Note: the interface takes `system_prompt` and `user_message` separately (not a single assembled string). This matches the `/api/chat` format and makes the intent clear.

#### `app/llm/ollama_provider.py`

Calls Ollama `/api/chat`. No LangChain — direct `httpx` call.

```python
import httpx
from app.llm.base import LLMProvider
from app.config import settings

class OllamaProvider(LLMProvider):
    def generate(self, system_prompt: str, user_message: str) -> str:
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "options": {
                "temperature": settings.llm_temperature,
                "num_predict": settings.llm_max_tokens,
            },
            "stream": False,
        }
        response = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
```

**Verify**: Call `OllamaProvider().generate("You are helpful.", "Say hello.")` and confirm you get a response. This is the minimal LLM smoke test.

#### `app/llm/parser.py`

Extracts `[cite: ...]` markers from the raw LLM response.

```python
import re
from app.api.schemas import Citation

CITE_PATTERN = re.compile(
    r'\[cite:\s*([^,\]]+),\s*p\.(\d+),\s*"([^"]+)"\]'
)

def extract_citations(text: str) -> list[Citation]:
    return [
        Citation(
            source_file=m.group(1).strip(),
            page_number=int(m.group(2)),
            section_heading=m.group(3).strip(),
        )
        for m in CITE_PATTERN.finditer(text)
    ]
```

**Verify**: Run `extract_citations('...temperature is 85°C [cite: X200_datasheet.pdf, p.4, "4.1 Thermal Specifications"]...')` and confirm one `Citation` object is returned with correct fields.

---

### Step 7 — Prompt assembler

**What**: Implement `app/prompts/assembler.py`. Assembles the full prompt from templates and retrieved chunks.

```python
from pathlib import Path
from app.config import settings

PROMPTS_DIR = Path("prompts")

def _load_template(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")

def build_system_prompt(role: str) -> str:
    base = _load_template(PROMPTS_DIR / "system" / "base.md")
    role_template = _load_template(PROMPTS_DIR / "roles" / f"{role}.md")
    return f"{base}\n\n{role_template}"

def build_user_message(query: str, chunks: list[dict]) -> str:
    context_blocks = []
    for chunk in chunks:
        block = (
            f'[Source: {Path(chunk["source_file"]).name} | '
            f'Page {chunk["page_number"]} | '
            f'Section: {chunk["section_heading"]}]\n'
            f'{chunk["text"]}'
        )
        context_blocks.append(block)
    context = "\n\n".join(context_blocks)
    return f"Context:\n\n{context}\n\nQuestion: {query}"
```

Note: `build_system_prompt` raises `FileNotFoundError` if the role template is missing — this is intentional, not a bug to fix.

**Verify**: Call `build_system_prompt("tech_service")` and print the result. It should be the concatenated base + tech_service templates. Call `build_user_message("test question", [sample_chunk])` and verify the source label format is correct.

---

### Step 8 — Pydantic schemas

**What**: Create `app/api/schemas.py` with the models defined in `MVP_ARCHITECTURE.md`. This file has no dependencies on other app modules — create it before the routes.

Copy the models from the architecture document exactly. The `Role` enum values must exactly match the prompt template filenames in `prompts/roles/`.

**Verify**: `python -c "from app.api.schemas import AskRequest, Role; print(list(Role))"` prints all six roles.

---

### Step 9 — FastAPI application

**What**: Implement `app/api/main.py` and `app/api/routes.py`. At the end of this step the API is running.

#### `app/api/routes.py`

Three routes:

**`POST /api/ask`**:
1. Validate request (Pydantic handles this)
2. Call `retriever.retrieve(query, top_k, product_family)`
3. If no results: return `AskResponse(answer=None, citations=[], no_results=True, ...)`
4. Call `assembler.build_system_prompt(role)` and `assembler.build_user_message(query, chunks)`
5. Call `OllamaProvider().generate(system_prompt, user_message)`
6. Call `parser.extract_citations(raw_response)` to get citations
7. If citations is empty: see fallback strategy below
8. Return `AskResponse`

**Citation fallback** (when model returns no `[cite: ...]` markers): rather than re-prompting (adds latency and complexity), extract citations from the context chunks themselves — every chunk that was included in the prompt becomes a citation. This is less precise than inline citations but always returns something. Mark these with a note in the response or log.

**`POST /api/ingest`**:
1. Load all PDFs from `request.path` (default `data/raw/`)
2. Split into chunks
3. Enrich with metadata
4. Save JSONL to `data/processed/`
5. Embed and upsert to ChromaDB
6. Return `IngestResponse` with counts and any errors

**`GET /api/health`**:
1. Check Ollama reachable: `GET /api/tags` on Ollama — if it returns 200, it's up
2. Check ChromaDB: `collection.count()` — if no exception, it's ok
3. Return status dict

#### `app/api/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: log readiness, optionally warm up models
    yield
    # shutdown: nothing needed

app = FastAPI(title="factory-rag-assistant", lifespan=lifespan)
app.include_router(router)
```

**Verify**: Run `uvicorn app.api.main:app --reload`. Open `http://localhost:8000/docs`. All three routes should appear. Call `GET /api/health` — it should return without error.

---

### Step 10 — CLI scripts

**What**: `scripts/ingest.py`, `scripts/chat.py`, `scripts/smoke_test.py`. These are thin wrappers — they call the app modules directly.

#### `scripts/ingest.py`

```python
# python scripts/ingest.py --path data/raw/ --doc-type manual --family X200
```
Calls the ingestion + embedding pipeline directly (not via the API). Prints a summary when done.

#### `scripts/chat.py`

```python
# python scripts/chat.py --role tech_service
```
Interactive loop: prompts for a question, calls the full pipeline, prints answer + citations. Exits on empty input or `quit`.

#### `scripts/smoke_test.py`

```python
# python scripts/smoke_test.py
```
Automated end-to-end check:
1. Ingest `data/raw/samples/sample_manual.pdf` (or the first PDF found in `data/raw/`)
2. Ask a question you know the answer to (hardcoded in the script)
3. Assert `response["answer"]` is not null
4. Assert `len(response["citations"]) > 0`
5. Print "PASS" or "FAIL" with the response

This script is the **definition of done for Phase 1**.

---

## Dependency and Test Order

Each step can only start after the previous is verified:

```
Step 1 (scaffolding)
    └─► Step 2 (ingestion)
            └─► Step 3 (JSONL write)
                    └─► Step 4 (embeddings + store)
                            └─► Step 5 (retrieval)
                                    └─► Step 6 (LLM provider)
                                            └─► Step 7 (prompt assembler)
                                                    └─► Step 8 (schemas)
                                                            └─► Step 9 (API)
                                                                    └─► Step 10 (scripts)
```

Do not skip verification at each step. Bugs in ingestion or retrieval will corrupt the LLM integration step — they are much harder to debug when three more layers are on top.

---

## First Real Documents

When the smoke test passes, the first task is to ingest real factory documents and manually verify quality:

1. Ingest 2–3 real PDFs with known content
2. Ask 5 questions you know the answers to
3. Check: are the right pages being retrieved? Are citations accurate?
4. If retrieval quality is poor, investigate before adding more documents

Retrieval debugging before adding documents is much cheaper than after.

---

## Common Pitfalls to Avoid

| Pitfall | Prevention |
|---|---|
| Ollama model tag is wrong | Verify with `ollama list` before writing any code |
| ChromaDB uses L2 instead of cosine | Set `{"hnsw:space": "cosine"}` at collection creation — cannot change later without dropping the collection |
| LangChain package not found | Import from `langchain_community`, `langchain_text_splitters`, `langchain_ollama`, `langchain_chroma` — not `langchain` |
| Chunk size is in characters not tokens | Document uses 1500 characters (≈ 300–400 tokens), not "512 tokens" |
| Prompt template missing silently | `assembler.py` raises `FileNotFoundError` — this is correct behavior |
| Data processed files committed | `data/processed/` and `data/embeddings/` are in `.gitignore` — never `git add` them |
| PyPDF page numbers are 0-indexed | Add 1 to `chunk.metadata["page"]` in `metadata.py` to make citations 1-indexed |
| Ollama streams by default | Always pass `"stream": false` in the request body |
