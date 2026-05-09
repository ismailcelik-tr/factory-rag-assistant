# ADR-003: nomic-embed-text as the Embedding Model

**Date**: 2025-01-15
**Status**: Accepted

---

## Context

Two embedding models were evaluated for the MVP: `nomic-embed-text` and `bge-m3`. Both are available via Ollama and are commonly used in local RAG systems. The decision must account for the 16GB RAM constraint on the development machine, where the embedding model and generative LLM run simultaneously.

## Decision

Use `nomic-embed-text` (via Ollama) as the embedding model for Phase 1 through Phase 2.

## Rationale

**RAM budget comparison**:

| Component | nomic-embed-text | bge-m3 |
|-----------|-----------------|--------|
| Embedding model | ~0.5 GB | ~2.5 GB |
| Gemma 4 4B (4-bit) | ~3.5 GB | ~3.5 GB |
| macOS + developer tools | ~4.0 GB | ~4.0 GB |
| Python process | ~0.8 GB | ~0.8 GB |
| **Total** | **~8.8 GB** | **~10.8 GB** |
| **Headroom** | **~7.2 GB** | **~5.2 GB** |

Both models fit. The choice comes down to whether bge-m3's quality advantage on English technical text justifies the 2GB RAM cost. It does not, for these reasons:

1. The document corpus is English-only. bge-m3's multilingual capability (its primary differentiator) is irrelevant.
2. On English technical retrieval benchmarks, both models perform comparably. bge-m3's higher overall BEIR score is driven by multilingual and cross-lingual tasks.
3. At MVP scale (likely < 10,000 chunks), retrieval quality differences between these models are not detectable without a proper eval dataset, which does not yet exist.
4. 2GB RAM matters on a shared developer machine. The headroom difference is the difference between smooth operation and occasional swap pressure.

## Consequences

- **Easier**: More RAM headroom for running browser, editor, and terminal alongside the inference stack.
- **Harder**: If the corpus later expands to multiple languages, bge-m3 would need to be adopted; all documents would need to be re-embedded.
- **Ruled out**: bge-m3 in Phase 1/2. Not permanently — it is the first embedding experiment to run in Phase 3 if hit rate falls below the 0.80 threshold.

## Review Trigger

Phase 3 evaluation: if retrieval hit rate @ 5 falls below 0.80 on `full_suite.jsonl`, switching to bge-m3 is the first experiment to run before any prompt or chunking changes.
