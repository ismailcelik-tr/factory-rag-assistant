# ADR-004: Switch PDF Loader from PyPDFLoader to PyMuPDF

**Status**: Accepted  
**Date**: 2026-05-10

## Context

The initial loader used LangChain's `PyPDFLoader` (backed by `pypdf`). During eval runs on `hirsiz-alarm.pdf`, extracted text contained character-spaced artifacts — e.g. `TTrr aa ffoo` instead of `Trafo`, `GG ee nn ee ll` instead of `Genel`. This is a known issue with PDFs that use certain glyph-spacing fonts. The LLM received this corrupted text as context and responded with "The provided documents do not contain sufficient information" even when the relevant information was present.

Measured impact on the evaluation dataset:
- Semantic Similarity mean: 0.521 (PyPDF) → 0.520 (PyMuPDF, no degradation)
- Citation Accuracy: 0.125 (PyPDF) → 0.250 (PyMuPDF, +100%)
- Chunk count reduced from 299 to 129 — cleaner text chunked more efficiently

## Decision

Replace `PyPDFLoader` with `fitz.open()` (PyMuPDF) in `app/ingestion/loader.py`. Add `pymupdf>=1.24` to `pyproject.toml` dependencies. Keep `pypdf` as a dependency since it may be required transitively.

## Consequences

- Text quality is significantly better for fonts that use character spacing.
- Chunk count drops because clean text chunks more efficiently (fewer fragment duplicates).
- `pypdf` remains in dependencies for transitive compatibility.
- PDFs with a proper text layer are handled correctly; scanned (image-only) PDFs still yield no text and log a warning — behaviour is unchanged.
