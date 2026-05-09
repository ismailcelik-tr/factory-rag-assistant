# ADR-001: Local-First LLM with Gemma 4 via Ollama

**Date**: 2025-01-15
**Status**: Accepted

---

## Context

Factory environments frequently operate under data residency constraints or network isolation requirements. The project must function without sending document content to external APIs. At the same time, development and iteration speed matter for a portfolio project.

## Decision

Use Gemma 4 via Ollama as the default and primary LLM. All LLM calls go through an abstracted provider interface so cloud models can be substituted without changing application logic.

## Rationale

**Alternatives considered**:

| Option | Why rejected |
|--------|-------------|
| Claude API (cloud) | Requires internet; document content leaves the network |
| GPT-4o (cloud) | Same concern; higher cost per query during development |
| Llama 3 via Ollama | Gemma 4 shows better instruction-following on procedural text in early tests |
| Self-hosted vLLM | Higher infrastructure overhead for a portfolio/prototype stage |

Gemma 4 via Ollama requires only a local GPU or CPU with sufficient RAM, has no per-token cost, and the Ollama REST API is stable enough to build a clean provider abstraction on top of.

## Consequences

- **Easier**: Development without API costs or rate limits; data stays local; offline use.
- **Harder**: Answer quality ceiling is lower than frontier cloud models; requires users to have Ollama installed.
- **Ruled out**: Cloud-only deployment without modification (by design — requires adding a cloud provider implementation).

## Review Trigger

If Gemma 4 is superseded by a significantly better open-weight model, or if a production deployment requires SLA-grade uptime that local inference cannot provide.
