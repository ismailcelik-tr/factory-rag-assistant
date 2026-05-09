# Architecture Overview

## System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        INGESTION PIPELINE                        │
│                                                                   │
│  data/raw/  ──►  Parser  ──►  Chunker  ──►  data/processed/     │
│  (PDFs,           (text +       (512-tok      (JSONL chunks +    │
│   DOCX,           page no.)     semantic)      metadata)         │
│   XLSX)                                                           │
└─────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                         INDEXING PIPELINE                         │
│                                                                   │
│  data/processed/  ──►  Embedding Model  ──►  Vector Store        │
│  (JSONL chunks)         (nomic-embed-text     (ChromaDB,         │
│                          via Ollama)           data/embeddings/)  │
└─────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┘
                    │                Query + Role
                    ▼                     │
┌───────────────────────────────────────────────────────────────┐
│                         QUERY PIPELINE                          │
│                                                                  │
│  Retriever  ──►  Context Assembly  ──►  Role Prompt Router      │
│  (top-k         (select chunks,         (load prompts/          │
│  cosine sim)     format citations)       roles/<role>.md)        │
│                                               │                  │
│                                               ▼                  │
│                                        LLM Interface             │
│                                        ├── Gemma 4 (Ollama)     │
│                                        └── Cloud LLM (future)   │
│                                               │                  │
│                                               ▼                  │
│                                   Answer + Citations JSON        │
└───────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┘
                    ▼
┌───────────────────────────────────────────────────────────────┐
│                       INTERFACE LAYER                            │
│                                                                  │
│  CLI (scripts/chat.py)  │  REST API (FastAPI)  │  Web UI        │
│                          │  (app/api/)           │  (future)     │
└───────────────────────────────────────────────────────────────┘
```

## Data Flow Summary

1. Raw documents land in `data/raw/` (manual copy or future upload endpoint)
2. Ingestion pipeline parses, cleans, and chunks them → `data/processed/`
3. Embedding pipeline embeds chunks and upserts to ChromaDB → `data/embeddings/`
4. At query time: user query + role → retriever → top-k chunks → role prompt assembly → LLM → JSON answer with citations
5. The API layer serves the JSON answer to the web UI or mobile client

## Key Interfaces

### LLM Provider Interface (`app/llm/`)

All LLM calls go through a single abstract interface. Implementations:
- `OllamaProvider` — calls local Ollama REST API (default)
- `ClaudeProvider` — calls Anthropic API (future)
- `OpenAIProvider` — calls OpenAI API (future)

Provider is selected by configuration. No caller outside `app/llm/` knows which provider is active.

### Vector Store Interface (`app/embeddings/`)

Abstracts ChromaDB for now. Can be replaced with Qdrant, Weaviate, or pgvector without touching retrieval logic.

## Decisions Log

All significant architectural decisions are recorded as ADRs in `architecture/decisions/`. See `decisions/TEMPLATE.md` to add a new one.
