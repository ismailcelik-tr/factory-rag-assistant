# TECH_STACK_DECISION.md

An honest evaluation of the proposed MVP stack. Each component is either accepted, accepted with modification, or replaced — always with explicit reasoning. No component is accepted just because it was proposed.

---

## Evaluation Summary

| Component | Proposed | Decision | Change |
|-----------|----------|----------|--------|
| Backend | FastAPI | **Accepted** | None |
| RAG framework | LangChain | **Accepted with scope limit** | Use for loading/splitting only |
| Vector DB | ChromaDB | **Accepted** | Already decided in ADR-002 |
| LLM | Ollama + Gemma 4 | **Accepted** | Already decided in ADR-001 |
| Embeddings | bge-m3 or nomic-embed-text | **nomic-embed-text chosen** | See RAM budget below |
| Frontend | Next.js later | **Accepted** | Out of MVP scope |
| Runtime | MacBook Pro 16GB | **Accepted** | Shapes model variant choice |

---

## Component-by-Component Reasoning

### FastAPI — Accepted

FastAPI is the right choice here without qualification.

- Automatic OpenAPI docs from type hints (portfolio value — the API is self-documenting)
- Async support for non-blocking LLM calls
- Pydantic validation for request/response schemas, which forces explicit contracts on role, query, and answer types
- Lightweight — no framework overhead at prototype scale

No changes.

---

### LangChain — Accepted with scope limit

LangChain is useful but dangerous to use uncritically. The useful parts and the dangerous parts are different layers of the library.

**Use LangChain for**:
- `PyPDFLoader`, `UnstructuredFileLoader` — stable document loaders that handle PDF page extraction and metadata correctly
- `RecursiveCharacterTextSplitter` — proven chunking with sentence-boundary awareness; saves real implementation work
- `OllamaEmbeddings` — thin wrapper for the Ollama embeddings API
- `Chroma` (LangChain's ChromaDB integration) — handles collection creation and upsert

**Do not use LangChain for**:
- `RetrievalQA`, `ConversationalRetrievalChain`, `create_retrieval_chain`, or any chain abstraction — these hide the prompt from the developer, make role-based prompt routing awkward, produce opaque debugging sessions, and reduce portfolio value because the interviewer cannot see your retrieval and prompt logic
- Any `Agent` or `Tool` abstraction from LangChain — out of scope and adds complexity with no MVP benefit

**The pattern to follow**: Use LangChain to get documents into ChromaDB. Write your own retrieval query, prompt assembly, and LLM call. This keeps the code readable and the architecture explicit.

**Version note**: Pin LangChain to a specific version in `pyproject.toml`. LangChain has a history of breaking changes between minor versions. Do not use `>=` bounds.

---

### ChromaDB — Accepted

Already decided in ADR-002. In-process, no separate service, metadata filtering, Python-native. The right choice for a local MVP.

---

### Ollama + Gemma 4 — Accepted

Already decided in ADR-001. The key implementation detail for 16GB RAM: use the smallest available Gemma 4 variant (4B or equivalent). The 12B variant will likely cause swap thrashing when the embedding model is also loaded.

Verify with: `ollama ps` while running a query to watch VRAM/RAM consumption before committing to a larger variant.

---

### Embedding Model: nomic-embed-text chosen over bge-m3

This is the only place where the proposal offered a genuine choice. The decision matters because of the 16GB RAM constraint.

**RAM budget at query time** (when both models must be loaded simultaneously):

| Component | nomic-embed-text | bge-m3 |
|-----------|-----------------|--------|
| Embedding model | ~0.5 GB | ~2.5 GB |
| Gemma 4 (4B, 4-bit) | ~3.5 GB | ~3.5 GB |
| macOS baseline | ~3.5 GB | ~3.5 GB |
| Python + app | ~1.0 GB | ~1.0 GB |
| **Total** | **~8.5 GB** | **~10.5 GB** |
| **Headroom** | **~7.5 GB** | **~5.5 GB** |

Both fit on 16GB. The difference is whether you have breathing room when the browser, editor, and terminal are also open. On a developer machine that is not a dedicated inference server, nomic-embed-text leaves significantly more headroom.

**Technical comparison**:

| Property | nomic-embed-text | bge-m3 |
|----------|-----------------|--------|
| Dimensions | 768 | 1024 |
| Multilingual | No (English-focused) | Yes |
| BEIR benchmark | Strong | State-of-the-art |
| RAM (loaded) | ~0.5 GB | ~2.5 GB |
| Ollama pull | `ollama pull nomic-embed-text` | `ollama pull bge-m3` |

**Decision rationale**: Factory documents in this project are single-language technical content. bge-m3's multilingual support and higher BEIR score are real advantages — but not advantages that are observable at MVP scale with a small document corpus. The extra 2GB RAM cost is a concrete cost today. The quality advantage over nomic-embed-text on English technical text is marginal and unproven without eval data.

**Reversal condition**: If eval results (Phase 3) show retrieval hit rate below 0.75 with nomic-embed-text, switching to bge-m3 is the first experiment to run. The abstracted embedding interface makes this a one-line config change.

This decision is recorded in ADR-003 (see `architecture/decisions/ADR-003-embedding-model.md`).

---

### No Docker in MVP — Confirmed

Docker adds real overhead with no benefit for a single-developer local project:
- No service isolation needed — all components run in-process or via Ollama's native daemon
- No deployment target in MVP — it runs on your laptop
- Adds complexity to the development loop (rebuild container to test a code change)

Docker becomes relevant when the FastAPI server needs to be deployed somewhere, or when onboarding a second developer. Not before.

---

### No Frontend in MVP — Confirmed

The API endpoint is the interface. A well-structured FastAPI with automatic Swagger docs is sufficient for development and demonstration. Adding Next.js before the RAG pipeline is proven is premature — the UI should be built on top of a working API, not alongside an untested one.

---

## What This Stack Is Not

- Not a scalable multi-user deployment
- Not a production system (no auth, no rate limiting, no monitoring in MVP)
- Not cloud-connected (intentionally)

These are all acknowledged constraints for Phase 1. See `docs/ROADMAP.md` for when each is addressed.
