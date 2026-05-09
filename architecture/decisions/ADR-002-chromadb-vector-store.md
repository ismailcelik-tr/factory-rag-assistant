# ADR-002: ChromaDB as the Initial Vector Store

**Date**: 2025-01-15
**Status**: Accepted

---

## Context

The system needs a vector store for storing and querying document embeddings. At the prototype stage, operational simplicity matters more than horizontal scalability.

## Decision

Use ChromaDB (persistent local mode) as the vector store, accessed through an abstracted interface in `app/embeddings/`.

## Rationale

**Alternatives considered**:

| Option | Why not chosen now |
|--------|-------------------|
| Qdrant | More operationally complex (separate process/Docker); better for production scale |
| Weaviate | Same — excellent product but overkill for < 100k chunks |
| pgvector | Requires PostgreSQL setup; adds dependency for a prototype |
| FAISS | File-based, no metadata filtering, harder to update incrementally |
| Pinecone | Cloud-only; same data residency concern as cloud LLM |

ChromaDB runs in-process with Python, persists to disk, supports metadata filtering, and requires no separate service. The abstraction layer means swapping to Qdrant or pgvector later requires only a new implementation class.

## Consequences

- **Easier**: Zero-config local setup; Python-native; metadata filtering works out of the box.
- **Harder**: Not suitable for multi-node production deployment; no native replication.
- **Ruled out**: Distributed vector search without switching to a different store (by design for v1).

## Review Trigger

If the document corpus exceeds ~500,000 chunks, or if a multi-user production deployment requires concurrent write access or replication.
