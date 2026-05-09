# `embedding-agent`

**One-line description**: Generates vector embeddings for processed chunks and upserts them into the vector store.

## Responsibility

Reads JSONL chunk files from `data/processed/`, calls the configured embedding model (default: `nomic-embed-text` via Ollama), and upserts vectors with their metadata into the local ChromaDB vector store at `data/embeddings/`. Produces a run log. Does not perform chunking, retrieval, or LLM inference.

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `input_path` | string | no | Path to specific JSONL file; omit to process all files in `data/processed/` |
| `embedding_model` | string | no | Default: `nomic-embed-text` (Ollama) |
| `store_path` | string | no | Default: `data/embeddings/` |
| `batch_size` | int | no | Embedding batch size (default: 64) |

## Outputs

- Updated ChromaDB collection at `data/embeddings/`
- Run log at `data/embeddings/runs/<timestamp>.json`:

```json
{
  "timestamp": "2025-01-15T14:32:00Z",
  "model": "nomic-embed-text",
  "chunks_processed": 1247,
  "chunks_upserted": 1247,
  "errors": []
}
```

## Preconditions

- Processed JSONL files exist in `data/processed/`
- Ollama is running locally with `nomic-embed-text` pulled (or alternative model configured)
- `data/embeddings/` directory exists

## Does NOT Do

- Chunk or process raw documents
- Perform retrieval queries
- Call any generative LLM
- Modify `data/processed/` files

## Example Invocation

```
Agent({
  subagent_type: "embedding-agent",
  prompt: "Embed all chunks in data/processed/ using nomic-embed-text"
})
```

## Related

- Upstream: `ingestion-agent` produces the JSONL files
- Downstream: `retrieval-agent` queries the vector store this agent writes
