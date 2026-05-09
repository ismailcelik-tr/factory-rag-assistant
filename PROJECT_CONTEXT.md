# PROJECT_CONTEXT.md

This document captures the "why" behind every significant design choice. It is the primary reference for any AI agent or engineer joining the project — read it before touching architecture or prompts.

---

## Problem Statement

Factory environments produce large volumes of heterogeneous technical documents. Technicians, sales staff, and engineers each need different slices of that knowledge, but documents are scattered, dense, and written for a specialist audience. The assistant bridges the gap: ask a question in plain language, get a concise, role-appropriate answer with a direct citation to the source page.

---

## User Profiles and What They Need

The system routes every query through a role-aware prompt. Six profiles are defined:

| Role | Primary Need | Tone |
|------|-------------|------|
| R&D Engineer | Deep technical accuracy, spec values, tolerances | Technical, precise |
| Technical Service | Step-by-step procedures, fault codes, safety warnings | Procedural, safety-first |
| Sales Representative | Benefits, compatibility, competitive differentiators | Concise, persuasive |
| Purchasing Specialist | Part numbers, lead times, pricing references, compliance | Factual, structured |
| Production / Operations | Setup, maintenance intervals, throughput limits | Operational, brief |
| Customer Support | Simplified explanations, warranty info, escalation paths | Plain language, reassuring |

Role is passed at query time (from UI session or API header). The system never guesses — if no role is provided, it falls back to a neutral technical voice.

---

## Document Corpus

Supported document types:

- User manuals (PDF)
- Product datasheets (PDF, occasionally Excel)
- Technical service documents (PDF, Word)
- Installation guides (PDF)
- Troubleshooting guides (PDF)
- Sales / technical specification sheets (PDF)

Documents are stored in `data/raw/`, processed to `data/processed/` (cleaned text + metadata), and indexed to `data/embeddings/`.

Each chunk carries metadata: `source_file`, `page_number`, `section_heading`, `document_type`, `product_family`. Citations are built from this metadata.

---

## Architecture Decisions

### 1. Local-First LLM

**Decision**: Gemma 4 via Ollama as the default inference backend.

**Why**: Many factory environments have strict data residency requirements. Running locally eliminates any question about sensitive document content leaving the network. Gemma 4 strikes a practical balance between quality and hardware requirements for a local deployment.

**Trade-off**: Lower raw capability than frontier cloud models. Mitigated by tight prompt engineering, small context windows with high-precision retrieval, and an abstracted LLM interface that allows cloud escalation.

### 2. Abstracted LLM Interface

**Decision**: All LLM calls go through a single provider interface (`app/llm/`). Gemma via Ollama and cloud APIs (Claude, OpenAI) are interchangeable implementations.

**Why**: Avoids vendor lock-in. Allows A/B testing of models against the same eval set without rewriting retrieval or prompt logic.

### 3. Role-Based Prompt Routing

**Decision**: Role is a first-class input to the prompt assembly step, not a post-processing filter.

**Why**: Injecting role context at prompt construction time gives the model the full frame before it generates. Post-filtering often produces answers that were generated for the wrong audience and then trimmed — lower quality and less reliable.

### 4. Chunking Strategy

**Decision**: `RecursiveCharacterTextSplitter` (LangChain), 512-token target, 64-token overlap, sentence boundaries, separators `["\n\n", "\n", ". ", " "]`.

**Why**: Fixed-size character splitting loses sentence context. Recursive splitting tries paragraph → sentence → word boundaries in order, which matches PDF document structure. 512 tokens matches nomic-embed-text's context window exactly.

**To be validated**: Phase 3 evaluation will test 256 and 768 token variants against a ground-truth dataset. No chunk size change is adopted without a before/after metric comparison.

### 5. Citations as a First-Class Feature

**Decision**: Every answer must include citations. Citations are not optional or stylistic.

**Why**: Factory staff making decisions based on a manual excerpt need to trust and verify the answer. A citation to page 34 of the technical service document is actionable. A floating answer is not.

### 6. Evaluation Before Optimisation

**Decision**: Build the eval harness alongside the retrieval pipeline, not after.

**Why**: Without a ground-truth dataset, every tuning decision (chunk size, top-k, reranker, prompt length) is a guess. The eval set is small initially (20–50 hand-authored QA pairs) but forces explicit quality targets from day one.

---

## What This Project Is Not

- Not a general-purpose chatbot. It is scoped to factory document knowledge.
- Not a document management system. `data/raw/` is a working directory, not a DMS replacement.
- Not a production deployment. This is a portfolio-quality proof of concept designed to be extended into production by a team.

---

## Roadmap

### Phase 1 — Working MVP (current)
- [x] Repository structure and documentation
- [x] Tech stack decided and documented (`docs/TECH_STACK_DECISION.md`)
- [x] MVP architecture defined (`architecture/MVP_ARCHITECTURE.md`)
- [ ] Document ingestion pipeline (`app/ingestion/`)
- [ ] Embedding generation and vector store (`app/embeddings/`)
- [ ] Retrieval (`app/retrieval/`)
- [ ] LLM provider interface (`app/llm/`)
- [ ] Prompt assembler (`app/prompts/`)
- [ ] FastAPI application (`app/api/`)
- [ ] CLI scripts and smoke test

### Phase 2 — Role Routing + API Hardening
- [ ] All six role prompts validated on real documents
- [ ] API versioning (`/api/v1/`)
- [ ] Structured logging
- [ ] Stable API reference (`docs/API.md`)

### Phase 3 — Quality and Evaluation
- [ ] Ground-truth QA dataset (50+ questions)
- [ ] Evaluation harness (`evals/run_evals.py`)
- [ ] Retrieval metrics (hit rate, MRR)
- [ ] Reranking and chunking experiments

### Phase 4 — Extension
- [ ] Web UI (Next.js)
- [ ] Cloud LLM fallback (Claude / OpenAI provider)
- [ ] Document upload via API
- [ ] Auth and role identity from session
- [ ] Mobile API documentation

---

## Key Constraints

- No secrets or credentials committed to the repository
- No fake production metrics or performance claims
- Evaluation must back any claim about retrieval or answer quality
- Every architectural change requires an ADR in `architecture/decisions/`
