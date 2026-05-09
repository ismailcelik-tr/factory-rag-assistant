# factory-rag-assistant

A production-grade Retrieval-Augmented Generation (RAG) assistant for factory operations, built as a professional AI engineering showcase.

The system ingests factory documents — user manuals, datasheets, service guides, installation instructions, troubleshooting documents, and technical specification sheets — and answers questions through a role-aware chat interface powered by a local LLM (Gemma 4 via Ollama).

---

## What This Project Demonstrates

- End-to-end RAG pipeline: ingestion → chunking → embeddings → vector search → answer generation
- Role-based prompt routing for six user profiles (R&D, technical service, sales, purchasing, production, customer support)
- Source citations in every answer
- Local-first LLM with a clean interface for swapping in cloud models
- Agent-driven development workflow using Claude Code skills and subagents
- Evaluation harness for retrieval quality and answer accuracy

---

## Architecture at a Glance

```
factory documents
      │
      ▼
  Ingestion & Chunking
      │
      ▼
  Embedding Model  ──►  Vector Store
                              │
  User Query  ──────►  Retriever
  + Role Profile              │
                              ▼
                     Context Assembly
                              │
                              ▼
                    Role-Aware Prompt Router
                              │
                              ▼
                   Gemma 4 (Ollama)  /  Cloud LLM
                              │
                              ▼
                  Answer + Citations
                              │
                              ▼
                        Chat UI  /  Mobile API
```

Full architecture decisions are documented in [`architecture/`](architecture/).

---

## Repository Layout

| Path | Purpose |
|------|---------|
| `app/` | Application code (ingestion pipeline, retrieval, API, UI) |
| `agents/` | Claude Code subagent definitions |
| `skills/` | Reusable Claude Code skill definitions |
| `prompts/` | System and role-specific prompt templates |
| `data/` | Raw documents, processed chunks, embedding artefacts |
| `evals/` | Evaluation datasets and harness |
| `docs/` | Design decisions, ADRs, onboarding guides |
| `architecture/` | Diagrams and architecture decision records |
| `scripts/` | Utility scripts (seeding, migration, tooling) |

---

## Getting Started

> Prerequisites and setup commands will be added once the application layer is scaffolded. See [`docs/setup.md`](docs/setup.md).

---

## Development Workflow

This project is built with an AI-native workflow. Key entry points for Claude Code:

- **`CLAUDE.md`** — instructions for Claude Code when working in this repo
- **`AGENTS.md`** — subagent definitions and task routing
- **`PROJECT_CONTEXT.md`** — the "why" behind every major decision
- **`skills/`** — reusable skill definitions invoked via `/skill-name`

---

## LLM Strategy

| Tier | Model | When |
|------|-------|------|
| Local (default) | Gemma 4 via Ollama | Development, privacy-sensitive workloads |
| Cloud (optional) | Claude / GPT-4o | Higher accuracy needs, production escalation |

The LLM interface is abstracted so either tier can be swapped without changing retrieval or routing logic.

---

## Status

Early scaffolding phase. See [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) for the roadmap.
