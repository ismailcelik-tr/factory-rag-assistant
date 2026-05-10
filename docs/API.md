# API Reference

## Versioning

| Version | Prefix | Status |
|---------|--------|--------|
| v1 | `/api/v1/` | **Primary — use this** |
| v0 | `/api/` | Legacy — functional, no new features |

All new integrations should use `/api/v1/`.

## Base URL

```
http://localhost:8000
```

---

## Endpoints

### POST /api/v1/ask

Ask a question against the indexed factory documents.

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `query` | string | Yes | 1–2000 characters |
| `role` | string (enum) | Yes | See [GET /api/v1/roles](#get-apiv1roles) |
| `product_family` | string | No | Filters retrieval to chunks tagged with this family |
| `session_id` | string | No | Opaque string; server accepts and ignores it. Use for client-side request correlation or local history management. |

**Response body (200 OK)**

| Field | Type | Notes |
|-------|------|-------|
| `answer` | string \| null | null when `no_results` is true |
| `citations` | Citation[] | Inline citations from the answer; fallback to context chunks if model omits markers |
| `role` | string | Echoed from request |
| `model` | string | LLM model name used |
| `chunks_used` | integer | Number of retrieved chunks included in the prompt |
| `no_results` | boolean | true when retrieval returned no matching chunks |

**Citation object**

| Field | Type |
|-------|------|
| `source_file` | string (basename) |
| `page_number` | integer (1-indexed) |
| `section_heading` | string |

**Request example**

```json
{
  "query": "What is the maximum operating temperature of the X200?",
  "role": "rd_engineer",
  "product_family": "X200",
  "session_id": "user-session-abc123"
}
```

**Response example — normal**

```json
{
  "answer": "The X200 has a maximum operating temperature of 85°C [cite: X200_datasheet.pdf, p.4, \"4.1 Thermal Specifications\"].",
  "citations": [
    {
      "source_file": "X200_datasheet.pdf",
      "page_number": 4,
      "section_heading": "4.1 Thermal Specifications"
    }
  ],
  "role": "rd_engineer",
  "model": "gemma4:e4b",
  "chunks_used": 5,
  "no_results": false
}
```

**Response example — no results**

```json
{
  "answer": null,
  "citations": [],
  "role": "rd_engineer",
  "model": "gemma4:e4b",
  "chunks_used": 0,
  "no_results": true
}
```

**Error responses**

| Status | `code` | Cause |
|--------|--------|-------|
| 422 | `validation_error` | Invalid role, empty query, or malformed JSON |

---

### GET /api/v1/roles

Returns the list of valid role identifiers. Use this to populate a role selector in a UI.

**Response body (200 OK)**

```json
{
  "roles": [
    "rd_engineer",
    "tech_service",
    "sales",
    "purchasing",
    "production",
    "customer_support"
  ]
}
```

---

### POST /api/v1/ingest

Ingest all PDF files from a directory into the vector store.

**Request body** (all fields optional — defaults apply)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `path` | string | `"data/raw/"` | Directory to scan for PDFs (recursive) |
| `document_type` | string | null | Override inferred type (e.g. `"manual"`, `"datasheet"`) |
| `product_family` | string | null | Tag applied to all chunks from this run |

**Response body (200 OK)**

| Field | Type | Notes |
|-------|------|-------|
| `files_processed` | integer | Number of PDFs successfully ingested |
| `chunks_created` | integer | Total chunks written to JSONL |
| `chunks_upserted` | integer | Total chunks upserted into ChromaDB |
| `errors` | string[] | Per-file error messages; non-empty but HTTP 200 means partial success |

**Request example**

```json
{
  "path": "data/raw/manuals/",
  "document_type": "manual",
  "product_family": "X200"
}
```

**Response example**

```json
{
  "files_processed": 3,
  "chunks_created": 847,
  "chunks_upserted": 847,
  "errors": []
}
```

**Note on partial failure**: If some files fail (e.g. scanned PDFs with no text layer), the response is still HTTP 200 but `errors` is non-empty. Check `files_processed` against the number of files you expected.

---

### GET /api/v1/health

Returns service status.

**Response body (200 OK)**

| Field | Type | Values |
|-------|------|--------|
| `status` | string | `"ok"` \| `"degraded"` |
| `ollama` | string | `"reachable"` \| `"unreachable"` |
| `vector_store` | string | `"ok"` \| `"error"` |
| `chunks_indexed` | integer | Current count in the ChromaDB collection |

**Response example — healthy**

```json
{
  "status": "ok",
  "ollama": "reachable",
  "vector_store": "ok",
  "chunks_indexed": 847
}
```

**Response example — degraded**

```json
{
  "status": "degraded",
  "ollama": "unreachable",
  "vector_store": "ok",
  "chunks_indexed": 847
}
```

---

## Error Response Format

All 4xx and 5xx responses use a consistent shape:

```json
{
  "error": "Human-readable description",
  "code": "machine_readable_code"
}
```

**Known error codes**

| Code | HTTP Status | Cause |
|------|-------------|-------|
| `validation_error` | 422 | Pydantic validation failed (invalid role, empty query, wrong types) |
| `http_404` | 404 | Route not found |
| `http_405` | 405 | Method not allowed |

---

## Role Reference

Each role receives the same retrieved context but a different system prompt that shapes tone, emphasis, and answer length.

| Role | Tone | Emphasis | Max length |
|------|------|----------|------------|
| `rd_engineer` | Technical, precise | Exact specs, tolerances, standards references | 600 tokens |
| `tech_service` | Procedural, safety-first | Numbered steps, fault codes, safety warnings | 300–500 tokens |
| `sales` | Concise, persuasive | Benefits, compatibility, differentiators | 200–300 tokens |
| `purchasing` | Factual, structured | Part numbers, lead times, compliance | 200–300 tokens |
| `production` | Operational, brief | Setup, maintenance intervals, throughput | 200–300 tokens |
| `customer_support` | Plain language, reassuring | Simplified explanations, warranty, escalation | 200–300 tokens |

---

## Legacy Routes (v0)

The following routes remain functional and will not be removed:

- `POST /api/ask`
- `POST /api/ingest`
- `GET /api/health`

They do not support `session_id`, the `/roles` endpoint, or structured logging. No new features will be added to v0 routes.
