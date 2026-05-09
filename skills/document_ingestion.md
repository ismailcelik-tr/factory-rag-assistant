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

- `.pdf` → PyMuPDF (preferred) or pdfplumber. Preserve page numbers.
- `.docx` → python-docx. Preserve headings.
- `.xlsx` / `.csv` → pandas. Treat each row as a record.

Cleaning rules:
- Strip headers, footers, page number artefacts
- Normalize whitespace (no consecutive blank lines > 1)
- Preserve section headings — they become chunk metadata

### 3. Detect section headings

Use heuristics appropriate to the file type:

- PDF: lines in larger font, all-caps, or followed by a blank line
- DOCX: elements with `Heading` style
- Fall back to line-length heuristics if structural markers are absent

Track the current heading as chunks are created.

### 4. Chunk the text

Target: **512 tokens**, overlap: **64 tokens**, boundary: sentence-level (never split mid-sentence).

```
while text remaining:
    take up to 512 tokens
    if mid-sentence, extend to sentence boundary (max +50 tokens)
    record chunk with current heading and page number
    step back 64 tokens for overlap
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
| Scanned PDF (no text layer) | Log a warning, skip the file, report to user — do not attempt OCR silently |
| Heading detection fails | Use `"[No Heading]"` — never leave blank, never guess |
| Token count exceeds hard cap | Raise an error with the offending chunk ID |
| Mixed-language document | Log a warning, proceed — language detection is not in scope for v1 |

---

## Related

- Agent: `ingestion-agent`
- Downstream skill: `evaluation` (for validating chunk quality)
