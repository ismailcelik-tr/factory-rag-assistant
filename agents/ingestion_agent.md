# `ingestion-agent`

**One-line description**: Converts raw factory documents into structured, metadata-enriched text chunks ready for embedding.

## Responsibility

Reads PDF files from `data/raw/`, extracts clean text, applies character-based chunking (1500 chars, 200 overlap), attaches metadata (document_type, product_family, section_heading, chunk_id), and writes JSONL chunk records to `data/processed/`. Does not generate embeddings or write to the vector store.

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `input_path` | string | yes | Path to file or directory in `data/raw/` |
| `document_type` | string | no | Override: `manual`, `datasheet`, `service`, `installation`, `troubleshooting`, `spec` |
| `product_family` | string | no | Tag all chunks with this product family identifier |
| `force` | bool | no | Reprocess even if output file already exists (default: false) |

## Outputs

JSONL file written to `data/processed/<source_filename>.jsonl`. Each line:

```json
{
  "chunk_id": "manual_x200_p012_003",
  "text": "...",
  "source_file": "data/raw/X200_user_manual.pdf",
  "page_number": 12,
  "section_heading": "3.2 Motor Calibration",
  "document_type": "manual",
  "product_family": "X200",
  "token_count": 487
}
```

## Preconditions

- Source file(s) exist in `data/raw/`
- PDF parsing dependency is installed (PyMuPDF / pdfplumber — TBD in setup)
- `data/processed/` directory exists

## Does NOT Do

- Generate embeddings
- Write to vector store
- Call any LLM
- Modify files in `data/raw/`

## Example Invocation

```
Agent({
  subagent_type: "ingestion-agent",
  prompt: "Process data/raw/X200_user_manual.pdf with document_type=manual and product_family=X200"
})
```

## Related

- Downstream: `embedding-agent` consumes the JSONL output
- Skill: `document-ingestion` (see `skills/document_ingestion.md`)
