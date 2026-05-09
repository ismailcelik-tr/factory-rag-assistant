# OPEN_DECISIONS.md

All Phase 1 decisions are resolved. The tracker at the bottom is the quick reference. Each entry below states the final decision and what it concretely means for implementation.

---

## OD-001 — LLM model tag ✅ RESOLVED

**Decision**: `gemma4:e4b`

Model is already available via Ollama (`ollama list` confirms it). All references updated.

**Applies to**:
- `app/config.py` default: `llm_model: str = "gemma4:e4b"`
- `CLAUDE.md` commands: `ollama pull gemma4:e4b`
- `architecture/MVP_ARCHITECTURE.md` memory budget table

---

## OD-002 — `pyproject.toml` with pinned dependencies ✅ RESOLVED

**Decision**: Create `pyproject.toml` as the first file. Use the package list below with minor-version pins (`x.y.*`). Do not use `langchain` base package — use the four split packages only.

```toml
[project]
name = "factory-rag-assistant"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi==0.115.*",
    "uvicorn[standard]==0.32.*",
    "pydantic==2.9.*",
    "pydantic-settings==2.6.*",
    "langchain-community==0.3.*",
    "langchain-text-splitters==0.3.*",
    "langchain-ollama==0.2.*",
    "langchain-chroma==0.1.*",
    "chromadb==0.5.*",
    "pypdf==5.*",
    "httpx==0.28.*",
]

[project.optional-dependencies]
dev = [
    "pytest==8.*",
    "ruff==0.8.*",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]
```

**Import paths to use** (not `langchain.*`):

| LangChain component | Import |
|---|---|
| `PyPDFLoader` | `from langchain_community.document_loaders import PyPDFLoader` |
| `RecursiveCharacterTextSplitter` | `from langchain_text_splitters import RecursiveCharacterTextSplitter` |
| `OllamaEmbeddings` | `from langchain_ollama import OllamaEmbeddings` |
| `Chroma` | `from langchain_chroma import Chroma` |

**Verify after install**: `python -c "from langchain_community.document_loaders import PyPDFLoader; print('ok')"` must print `ok`.

---

## OD-003 — Pipeline: JSONL stage vs. direct-to-ChromaDB ✅ RESOLVED

**Decision**: Two-stage pipeline. Ingestion writes JSONL to `data/processed/`. Embedding reads JSONL and writes to ChromaDB. These are two separate operations.

**Pipeline is**:
```
Loader → Splitter → Metadata Enricher → JSONL write (data/processed/)
                                              ↓
                                       Embedder → ChromaDB (data/embeddings/)
```

**Applies to**: `MVP_ARCHITECTURE.md` pipeline diagram must match this. `AGENTS.md` already matches.

---

## OD-004 — Chunking units ✅ RESOLVED

**Decision**: Character-based. `chunk_size=1500`, `chunk_overlap=200`. No tokenizer dependency.

```python
RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " "],
)
```

1500 characters ≈ 300–400 tokens for English technical text. This stays comfortably within nomic-embed-text's 512-token context window.

**Do not use** the phrase "512-token chunks" anywhere in the codebase or documentation. Use "~1500-character chunks" instead. Anywhere existing docs say "512 tokens" for chunk size, the value is wrong and must be updated.

---

## OD-005 — ChromaDB distance metric ✅ RESOLVED

**Decision**: Cosine similarity, set explicitly at collection creation.

```python
client.get_or_create_collection(
    name=settings.collection_name,
    metadata={"hnsw:space": "cosine"},
)
```

This line must appear in `store.py`. If it is absent, ChromaDB silently uses L2 distance and retrieval results are wrong. The metric cannot be changed after collection creation without dropping the collection and re-embedding all documents.

---

## OD-006 — Ollama API endpoint and request format ✅ RESOLVED

**Decision**: `POST /api/chat` with `"stream": false`.

```python
payload = {
    "model": settings.llm_model,
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message},
    ],
    "options": {
        "temperature": settings.llm_temperature,
        "num_predict": settings.llm_max_tokens,
    },
    "stream": False,
}
response = httpx.post(f"{settings.ollama_base_url}/api/chat", json=payload, timeout=120.0)
return response.json()["message"]["content"]
```

`stream: False` is mandatory — Ollama streams by default and the streaming response format is different. `timeout=120.0` is necessary; Gemma on CPU can take 30–90 seconds for a complex answer.

---

## OD-007 — Prompt assembly structure ✅ RESOLVED

**Decision**: System message = `base.md` + `"\n\n"` + role template. User message = formatted context blocks + `"\n\nQuestion: "` + query.

```
system_prompt = base.md content + "\n\n" + prompts/roles/<role>.md content
user_message  = "Context:\n\n" + [formatted chunk blocks] + "\n\nQuestion: " + query
```

Each context block is formatted as:
```
[Source: <filename> | Page <N> | Section: <heading>]
<chunk text>
```

The repetition of citation rules between `base.md` and the role template is intentional. Small models need the instruction reinforced in both the universal rules and the role persona.

If `prompts/roles/<role>.md` does not exist, `assembler.py` raises `FileNotFoundError`. This is correct — do not add a silent fallback.

---

## OD-008 — PDF heading detection approach ✅ RESOLVED

**Decision**: `PyPDFLoader` (plain text only) with plain-text heuristics. No PyMuPDF, no font detection.

**Heading detection heuristics** (applied to each chunk's text, scanning line by line before the first sentence-ending punctuation):

1. Line is all-uppercase and shorter than 60 characters
2. Line matches `r"^\d+(\.\d+)*\s+[A-Z]"` — e.g., `"3.2 Motor Calibration"`
3. Line matches `r"^(Section|Chapter|Part)\s+\d"` (case-insensitive)
4. If none of the above match: carry the last matched heading forward across chunks from the same document (tracked via an accumulator in the `enrich()` function)
5. If no heading has ever been found in the document: use `"[No Heading]"`

The `section_heading` field will be approximate for many documents. This is acceptable for MVP — citations still have accurate `source_file` and `page_number`. Heading accuracy is deferred to Phase 3 (possible upgrade: add PyMuPDF as an opt-in loader).

---

## OD-009 — Test document for smoke test ✅ RESOLVED

**Decision**: No sample PDF is committed to the repository. `scripts/smoke_test.py` uses the first `.pdf` file found in `data/raw/` (scanned recursively). The developer must place at least one PDF in `data/raw/` before running the smoke test.

This is documented in `docs/setup.md` under "First Run". Committing a sample PDF is unnecessary complexity (copyright questions, binary file in git, maintenance burden). Any PDF the developer already has works.

`smoke_test.py` fails immediately with a clear message if `data/raw/` contains no PDFs, rather than silently passing with no data.

---

## OD-010 — Citation `source_file` format ✅ RESOLVED

**Decision**: Store the full relative path in ChromaDB metadata (`data/raw/X200_user_manual.pdf`). Return only the basename in the API response `Citation` object (`X200_user_manual.pdf`).

`parser.py` uses `Path(raw_path).name` when constructing `Citation` objects from parsed `[cite: ...]` markers.

The LLM citation format instructs the model to use the filename only (not the full path), which is what `[cite: X200_user_manual.pdf, p.4, "..."]` already shows. The `source_file` field in `ChromaDB` metadata stores the full path for internal use. These two are reconciled in `parser.py`.

---

## OD-011 — Python package `__init__.py` files ✅ RESOLVED

**Decision**: Create empty `__init__.py` in every `app/` subdirectory as part of Step 1 scaffolding.

Required files:
- `app/__init__.py`
- `app/api/__init__.py`
- `app/ingestion/__init__.py`
- `app/embeddings/__init__.py`
- `app/retrieval/__init__.py`
- `app/llm/__init__.py`
- `app/prompts/__init__.py`

All are empty. Create before writing any other Python file.

---

## OD-012 — Config file naming ✅ RESOLVED

**Decision**: One config file: `app/config.py`. There is no `app/llm/config.py`.

The stale reference in `CLAUDE.md` has been corrected. All modules import from `app.config`.

---

## Decision Status Tracker

| ID | Title | Status | Final Decision |
|----|-------|--------|---------------|
| OD-001 | LLM model tag | ✅ Resolved | `gemma4:e4b` |
| OD-002 | `pyproject.toml` | ✅ Resolved | 4 LangChain split packages + chromadb 0.5 + httpx + pinned versions |
| OD-003 | Pipeline stages | ✅ Resolved | Two-stage: JSONL then ChromaDB |
| OD-004 | Chunk sizing units | ✅ Resolved | 1500 chars / 200 overlap, character-based |
| OD-005 | ChromaDB distance metric | ✅ Resolved | Cosine, `{"hnsw:space": "cosine"}` at creation |
| OD-006 | Ollama endpoint | ✅ Resolved | `/api/chat`, `stream: false`, timeout 120s |
| OD-007 | Prompt assembly | ✅ Resolved | system = base + role template; user = context + question |
| OD-008 | Heading detection | ✅ Resolved | PyPDFLoader + 3 plain-text regex heuristics + carry-forward |
| OD-009 | Smoke test document | ✅ Resolved | No committed sample; use first PDF found in data/raw/ |
| OD-010 | Citation source_file | ✅ Resolved | Store full path in ChromaDB; return basename in API |
| OD-011 | `__init__.py` files | ✅ Resolved | Empty files in all app/ subdirs, created in Step 1 |
| OD-012 | Config file naming | ✅ Resolved | `app/config.py` only; CLAUDE.md corrected |
