# Scripts

Utility entry points for pipeline stages. These are thin CLI wrappers over `app/` logic.

| Script | Purpose |
|--------|---------|
| `ingest.py` | Parse and chunk documents from `data/raw/` |
| `embed.py` | Generate embeddings and upsert to vector store |
| `chat.py` | Interactive CLI query interface |

Scripts will be created when the application layer is scaffolded. See `docs/setup.md` for usage.
