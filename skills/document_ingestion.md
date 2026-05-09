# Skill: `document-ingestion`

**Trigger**: When the user asks to process, parse, ingest, or chunk a document, or adds files to `data/raw/`.

---

## Purpose

Extract clean text from factory documents, split into meaningful chunks, and attach metadata. The output is a structured JSONL file ready for embedding.

---

## Steps

### 1. Identify document type

Check the filename and any user-provided context to classify the document:

| Keyword pattern | Document type |
|----------------|--------------|
| `manual`, `user_guide` | `manual` |
| `datasheet`, `data_sheet` | `datasheet` |
| `service`, `maintenance` | `service` |
| `installation`, `install` | `installation` |
| `troubleshoot`, `fault`, `error` | `troubleshooting` |
| `spec`, `specification`, `sales` | `spec` |

If ambiguous, ask the user before proceeding.

### 2. Extract text

Use the appropriate parser for the file type:

- `.pdf` → `PyPDFLoader` (LangChain). Returns plain text + page number per page. No font metadata.
- `.docx` → out of MVP scope; document for Phase 2
- `.xlsx` / `.csv` → out of MVP scope; document for Phase 2

Cleaning notes:
- `PyPDFLoader` returns raw extracted text. Some PDFs produce noisy output (hyphenated line breaks, extracted headers/footers mixed in). Accept this for MVP — cleaning is a Phase 3 improvement.
- PyPDF page numbers are 0-indexed. Add 1 in the metadata step.

### 3. Detect section headings

`PyPDFLoader` returns plain text only — no font size, no style information. Use plain-text heuristics only.

Scan each chunk's text line by line, looking for a heading before the first sentence-ending punctuation:

1. Line is all-uppercase and shorter than 60 characters → heading
2. Line matches `r"^\d+(\.\d+)*\s+[A-Z]"` (e.g. `"3.2 Motor Calibration"`) → heading
3. Line matches `r"^(Section|Chapter|Part)\s+\d"` (case-insensitive) → heading
4. If none match: carry the last matched heading forward across subsequent chunks from the same document
5. If no heading has ever matched in the document: use `"[No Heading]"`

These heuristics will miss headings in many real PDFs. That is acceptable for MVP — `source_file` and `page_number` are always accurate, and heading quality is a Phase 3 improvement (possible upgrade: PyMuPDF for font-based detection).

### 4. Chunk the text

Chunk size: **1500 characters**, overlap: **200 characters**.

`RecursiveCharacterTextSplitter.chunk_size` is in characters, not tokens. 1500 characters ≈ 300–400 tokens for English technical text. Do not add a tokenizer dependency to enforce token counts.

```python
RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " "],
)
```

### 5. Assign chunk IDs

Format: `<doc_type>_<product_family>_p<page>_<seq>`

Example: `manual_x200_p012_003`

If product family is unknown, use `unknown` and flag for review.

### 6. Write output

One JSONL file per source document at `data/processed/<source_stem>.jsonl`.

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

### 7. Validate output

Before finishing:
- Confirm no chunk has `token_count` > 600 (hard cap — raise an error, do not silently truncate)
- Confirm every chunk has a non-empty `section_heading` (use `"[No Heading]"` if none found, do not leave blank)
- Log: source file, total chunks, average token count, any parsing warnings

---

## What Can Go Wrong

| Problem | How to handle |
|---------|--------------|
| Scanned PDF (no text layer) | `PyPDFLoader` returns empty `page_content`. Log a warning, skip the file, report in ingest response — do not attempt OCR |
| Heading detection finds nothing | Use `"[No Heading]"` — never leave the field blank |
| Chunk character count > 2000 | Log a warning (soft limit — `RecursiveCharacterTextSplitter` enforces the split at 1500 chars, so this should not occur in practice) |
| Mixed-language document | Log a warning, proceed — language detection is not in scope for v1 |

---

## Related

- Agent: `ingestion-agent`
- Downstream skill: `evaluation` (for validating chunk quality)
