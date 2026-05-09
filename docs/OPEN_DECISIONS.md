# OPEN_DECISIONS.md

Decisions that must be made before or during Phase 1 implementation. Grouped by urgency.

Each entry states the issue clearly, the options available, and a recommended default. If the default is strong, follow it and close the decision. If genuine uncertainty exists, it is called out explicitly.

---

## Blockers — Resolve Before Writing Any Code

These will cause implementation to fail or produce silent correctness bugs if not resolved first.

---

### OD-001 — Verify Gemma 4 Ollama model tag

**Issue**: Every document uses `ollama pull gemma4` and `model: "gemma4"`, but Ollama model tags are version-specific and must match what Ollama actually registers. If the tag is wrong, every LLM call silently fails.

**Check**:
```bash
ollama pull gemma3          # Gemma 3 (confirmed available as of early 2025)
ollama list                 # shows what was actually registered
```

**Options**:
- If Gemma 4 is available on Ollama: confirm the exact tag (may be `gemma4`, `gemma4:4b`, `gemma4:latest`, or similar)
- If Gemma 4 is not yet on Ollama: use `gemma3:4b` and update all references

**Action**: Run `ollama pull gemma4` before writing any code. If it fails, fall back to `gemma3:4b`. Update `app/config.py` default and `CLAUDE.md` commands with the correct tag.

**Close condition**: `ollama list` shows the model as available, model name is confirmed in `app/config.py`.

---

### OD-002 — Create `pyproject.toml` with pinned dependencies

**Issue**: No `pyproject.toml` exists. `pip install -e ".[dev]"` cannot run. Nothing can be installed. This is a complete blocker.

**LangChain package fragmentation note**: LangChain has been split into separate packages. The correct imports are:

| What we need | Package to install | Import path |
|---|---|---|
| `PyPDFLoader` | `langchain-community` | `from langchain_community.document_loaders import PyPDFLoader` |
| `RecursiveCharacterTextSplitter` | `langchain-text-splitters` | `from langchain_text_splitters import RecursiveCharacterTextSplitter` |
| `OllamaEmbeddings` | `langchain-ollama` | `from langchain_ollama import OllamaEmbeddings` |
| `Chroma` (LangChain wrapper) | `langchain-chroma` | `from langchain_chroma import Chroma` |

**Required dependencies for MVP** (to be confirmed with actual install and import checks):

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
```

**Action**: Create `pyproject.toml` as the first file in Phase 1. Verify all imports work after `pip install -e ".[dev]"`.

**Close condition**: `python -c "from langchain_community.document_loaders import PyPDFLoader"` runs without error.

---

### OD-003 — Resolve pipeline architecture inconsistency: JSONL stage vs. direct-to-ChromaDB

**Issue**: Two documents contradict each other on whether `data/processed/` (JSONL) is part of the MVP pipeline.

- `AGENTS.md` and `skills/document_ingestion.md` describe a two-stage pipeline: ingestion writes JSONL to `data/processed/`, then embedding reads JSONL and writes to ChromaDB.
- `architecture/MVP_ARCHITECTURE.md` pipeline diagram goes directly: `Loader → Splitter → Metadata Enricher → Embedder → Vector Store`, with no JSONL step.

**Implications of each approach**:

| Approach | Pros | Cons |
|---|---|---|
| Two-stage (JSONL + ChromaDB) | Can re-embed without re-parsing; inspectable intermediate output; agents are cleanly separated | More moving parts; more code to write |
| Single-stage (direct to ChromaDB) | Simpler; fewer files; less code | Can't re-embed without re-parsing; no inspectable intermediate; breaks agent boundary in `AGENTS.md` |

**Recommendation**: **Two-stage** for MVP. The ability to re-embed without re-parsing matters when experimenting with embedding models in Phase 3. The JSONL files are also useful for debugging (you can read them in a text editor to verify chunking quality without querying ChromaDB). The extra code is one function in `ingestion-agent`.

**Action**: Update `MVP_ARCHITECTURE.md` pipeline diagram to include the JSONL write step between metadata enrichment and embedding. The pipeline becomes: `Loader → Splitter → Metadata → JSONL write → Embedder → ChromaDB`.

**Close condition**: `MVP_ARCHITECTURE.md` and `AGENTS.md` agree on the pipeline stages.

---

## Should Decide Before Writing Code

These are not outright blockers but will require awkward refactoring if decided wrong and discovered later.

---

### OD-004 — Character vs. token chunking

**Issue**: The architecture says "512-token target" for chunk size, but `RecursiveCharacterTextSplitter`'s `chunk_size` parameter is in characters by default. Without a custom `length_function`, you get ~512 characters — roughly 100–130 tokens — which is far smaller than intended.

**To get true token-based chunking**, you must pass a tokenizer as `length_function`:
```python
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")
splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=64,
    length_function=lambda text: len(enc.encode(text)),
)
```

**Alternatives**:
- Use token-based chunking with tiktoken (adds a dependency; requires a decision on which tokenizer to use — `cl100k_base` is OpenAI's, not Gemma's, but is a reasonable approximation)
- Use character-based chunking with a larger value (~2000 characters ≈ 512 tokens for English text) and accept approximate sizing
- Accept the discrepancy and use `chunk_size=2000` characters without calling it "tokens" in the documentation

**Recommendation**: Use **character-based chunking with `chunk_size=1500`, `chunk_overlap=200`**. This gives approximately 300–400 tokens per chunk for English technical text — within nomic-embed-text's 512-token context window — without adding a tokenizer dependency. Rename the parameter description in the docs from "512 tokens" to "~1500 characters (approx. 300–400 tokens)". This is simpler, transparent about what it actually does, and avoids a dependency on a tokenizer that is not otherwise needed.

**Action**: Decide which approach to use and update `MVP_ARCHITECTURE.md`, `PROJECT_CONTEXT.md`, and `skills/document_ingestion.md` to use consistent language.

**Close condition**: Chunk size parameter is specified in the same units everywhere, and the value used matches the unit.

---

### OD-005 — ChromaDB distance metric configuration

**Issue**: The architecture specifies "cosine similarity search" but ChromaDB defaults to squared L2 (Euclidean) distance. Without explicit configuration, retrieval results are scored differently than expected, and the top-k results may not be the same as they would be under cosine similarity. This is a silent correctness issue.

**Fix**: When creating the ChromaDB collection, specify the distance metric:
```python
collection = client.get_or_create_collection(
    name="factory_docs",
    metadata={"hnsw:space": "cosine"}
)
```

**Important**: This must be set at collection creation time. Changing it later requires deleting and recreating the collection and re-embedding all documents.

**Recommendation**: Always use cosine. Specify it explicitly. Document it in `store.py`.

**Action**: Add this to `store.py` implementation notes in `MVP_ARCHITECTURE.md`. Note that changing the metric requires a full re-embed.

**Close condition**: `MVP_ARCHITECTURE.md` specifies the ChromaDB cosine configuration explicitly.

---

### OD-006 — Ollama API endpoint and request format

**Issue**: The architecture says `POST localhost:11434` without specifying which Ollama endpoint. Ollama has two relevant endpoints:

| Endpoint | Format | Use case |
|---|---|---|
| `POST /api/generate` | `{model, prompt, stream}` | Single-turn completion; prompt is a raw string |
| `POST /api/chat` | `{model, messages: [{role, content}]}` | Chat format with system/user/assistant messages |

**For RAG use cases, `/api/chat` is better** because:
- The system prompt (base rules + role persona) maps naturally to `role: "system"`
- The user query maps to `role: "user"`
- The context blocks are injected into either the system or user message (see OD-007)
- Most Gemma fine-tunes are instruction-tuned for chat format, not raw completion

**Recommendation**: Use `/api/chat`. The assembled prompt becomes:
```json
{
  "model": "gemma4",
  "messages": [
    {"role": "system", "content": "<base rules> + <role template>"},
    {"role": "user", "content": "<context blocks>\n\nQuestion: <query>"}
  ],
  "options": {"temperature": 0.1},
  "stream": false
}
```

**Action**: Update `ollama_provider.py` implementation notes to specify `/api/chat` format. Add `"stream": false` explicitly (Ollama streams by default — if not disabled, the response handling must read a streaming response, which adds complexity with no MVP benefit).

**Close condition**: `MVP_ARCHITECTURE.md` specifies the Ollama endpoint, request format, and `stream: false`.

---

### OD-007 — How base system prompt and role template combine in `assembler.py`

**Issue**: Both `prompts/system/base.md` and `prompts/roles/<role>.md` exist, but `assembler.py`'s combination logic is never specified. Questions not answered anywhere:
- Does base come before or after the role template?
- Does the role template replace the base, or extend it?
- Does the context go in the system message or the user message?
- Does the base repeat rules that are already in the role template (e.g., both say "cite every claim") — is that intentional?

**Recommendation**: Use this structure for the Ollama `/api/chat` call:

```
system message = base.md content + "\n\n" + role_template.md content
user message   = formatted context blocks + "\n\nQuestion: " + query
```

**Rationale**:
- Base provides universal rules (no hallucination, citation format, context-only answers)
- Role template provides persona and audience-specific framing
- Context in the user message matches the conversational model — the "user" is providing the relevant excerpts and asking a question
- Repetition of citation rules across base and role is intentional redundancy: small models need the instruction reinforced

**Action**: Document this assembly structure explicitly in `MVP_ARCHITECTURE.md` under the prompt assembler section.

**Close condition**: `assembler.py`'s construction logic is described in `MVP_ARCHITECTURE.md` as a concrete string assembly specification.

---

### OD-008 — PDF loader for heading detection: PyPDFLoader vs. PyMuPDF

**Issue**: `skills/document_ingestion.md` describes heading detection using font size and formatting heuristics. But `PyPDFLoader` (LangChain) extracts plain text only — no font metadata. Font-based heading detection requires PyMuPDF (`fitz`), which is a separate library.

**Options**:

| Approach | Library | Heading quality | Complexity |
|---|---|---|---|
| Plain-text heuristics only | `PyPDFLoader` (already planned) | Low — all-caps, blank-line detection only | Simple |
| Font-based detection | `PyMuPDF` (`fitz`) | High — actual heading detection | Medium — need to write a custom loader |
| LangChain + PyMuPDF together | Both | High for headings, uses LangChain for splitting | Two PDF libraries |

**Recommendation**: **Plain-text heuristics via `PyPDFLoader` for MVP**. Accept that heading detection will be imprecise — many chunks will have `"[No Heading]"` or a parent section heading from a heuristic. This is acceptable for MVP: citations will still have accurate `source_file` and `page_number`. Heading accuracy is a quality improvement for Phase 3.

Update `skills/document_ingestion.md` to remove the font-size detection description (which is misleading given `PyPDFLoader`) and replace with the actual plain-text heuristics that will be implemented: look for lines that are short, followed by a newline, all-uppercase, or match common section number patterns like `"1.2 "`, `"Section 3"`.

**Action**: Remove font-based heading claims from `skills/document_ingestion.md`. Add plain-text heuristic specification.

**Close condition**: Heading detection approach in docs matches what `PyPDFLoader` can actually provide.

---

## Can Decide During Implementation

These do not require upfront decisions but should be documented once decided.

---

### OD-009 — Test document for smoke test

**Issue**: `scripts/smoke_test.py` ingests "one test PDF" but no test document exists in the repository. A developer starting fresh has nothing to test with.

**Options**:
- Commit a small public-domain or openly licensed factory-relevant PDF to `data/raw/samples/`
- Document that the developer must provide their own document
- Use a generated minimal PDF as a fixture

**Recommendation**: Commit a small sample document (1–3 pages) to `data/raw/samples/sample_manual.pdf`. Use a public-domain technical document or generate one specifically for testing. The smoke test should reference this file by path. This makes `scripts/smoke_test.py` runnable without any prerequisite action.

**Close condition**: `data/raw/samples/` contains at least one PDF, and `scripts/smoke_test.py` references it by relative path.

---

### OD-010 — Citation source_file format: filename only vs. relative path

**Issue**: The citation schema uses `source_file: str`. In metadata stored by the ingestion pipeline, `source_file` will be the full relative path (`data/raw/X200_user_manual.pdf`). In the citation format the LLM is instructed to produce, only the filename is used (`X200_user_manual.pdf`). `parser.py` will need to normalize between these two forms.

**Recommendation**: Store the relative path in ChromaDB metadata. In `parser.py`, extract the basename when building `Citation` objects. The API response `source_file` field returns the basename only (cleaner for the client). If a future UI needs to link to the actual file, the full path can be added as a separate field.

**Close condition**: `parser.py` implementation note in `MVP_ARCHITECTURE.md` specifies that `source_file` in the `Citation` object is the basename of the stored path.

---

### OD-011 — `app/` Python package structure

**Issue**: `app/` and its subdirectories are referenced as importable modules throughout the architecture (`from app.config import settings`, `from app.llm.base import LLMProvider`, etc.), but Python requires `__init__.py` files in each directory for these imports to work.

**Required `__init__.py` files**:
- `app/__init__.py`
- `app/api/__init__.py`
- `app/ingestion/__init__.py`
- `app/embeddings/__init__.py`
- `app/retrieval/__init__.py`
- `app/llm/__init__.py`
- `app/prompts/__init__.py`

All should be empty files. This is not an architectural decision — it is a mechanical requirement. Create them as part of the initial scaffolding step.

**Close condition**: All `__init__.py` files exist before the first `import` statement is written.

---

### OD-012 — Config file naming: `app/config.py` vs. `app/llm/config.py`

**Issue**: `CLAUDE.md` says "Provider configuration lives in `app/llm/config.py`" but `MVP_ARCHITECTURE.md` and the Pydantic settings block are in `app/config.py`. All settings — including LLM model name — belong in `app/config.py`. There is no separate `app/llm/config.py`.

**Action**: Fix the CLAUDE.md reference to remove the mention of `app/llm/config.py`. Only `app/config.py` exists.

**Close condition**: CLAUDE.md references `app/config.py` consistently.

---

## Decision Status Tracker

| ID | Title | Status |
|----|-------|--------|
| OD-001 | Gemma 4 Ollama model tag | Open — verify before first code |
| OD-002 | `pyproject.toml` with dependencies | Open — first file to create |
| OD-003 | JSONL stage vs. direct-to-ChromaDB | Recommended: two-stage |
| OD-004 | Character vs. token chunking | Recommended: characters (~1500) |
| OD-005 | ChromaDB distance metric | Recommended: cosine, explicit config |
| OD-006 | Ollama API endpoint | Recommended: `/api/chat`, stream: false |
| OD-007 | Prompt assembly structure | Recommended: system = base + role, user = context + query |
| OD-008 | PDF loader for heading detection | Recommended: PyPDFLoader + plain-text heuristics |
| OD-009 | Test document for smoke test | Open — commit a sample PDF |
| OD-010 | Citation source_file format | Recommended: basename in API response |
| OD-011 | `app/` Python package `__init__.py` | Mechanical — create all of them |
| OD-012 | Config file naming inconsistency | Fix CLAUDE.md reference |
