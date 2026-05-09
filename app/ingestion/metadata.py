"""Enrich split chunks with computed metadata fields.

Converts LangChain Documents into plain dicts suitable for JSONL storage
and ChromaDB ingestion.

Output schema per chunk:
  chunk_id       – "<doc_type>_<product_family>_p<page>_<seq>" (zero-padded)
  text           – chunk text
  source_file    – full relative path to the source PDF
  page_number    – 1-indexed (PyPDFLoader returns 0-indexed; +1 applied here)
  section_heading – detected heading or "[No Heading]"
  document_type  – inferred from filename or supplied explicitly
  product_family – supplied explicitly or "unknown"
  token_count    – word count (approximation; sufficient for validation)
"""

import json
import logging
import re
from pathlib import Path

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# --- Document-type inference from filename keywords -------------------------

_DOC_TYPE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"manual|user.?guide", re.IGNORECASE), "manual"),
    (re.compile(r"datasheet|data.?sheet", re.IGNORECASE), "datasheet"),
    (re.compile(r"service|maintenance", re.IGNORECASE), "service"),
    (re.compile(r"install", re.IGNORECASE), "installation"),
    (re.compile(r"troubleshoot|fault|error", re.IGNORECASE), "troubleshooting"),
    (re.compile(r"spec|specification|sales", re.IGNORECASE), "spec"),
]


def _infer_document_type(filename: str) -> str:
    stem = Path(filename).stem
    for pattern, doc_type in _DOC_TYPE_PATTERNS:
        if pattern.search(stem):
            return doc_type
    return "unknown"


# --- Heading detection heuristics -------------------------------------------

# Ordered by specificity: numbered section first, then keyword, then all-caps.
_HEADING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\d+(\.\d+)*\s+[A-Z]"),          # e.g. "3.2 Motor Calibration"
    re.compile(r"^(Section|Chapter|Part)\s+\d", re.IGNORECASE),  # e.g. "Section 4"
]


def _detect_heading(text: str) -> str | None:
    """Return the first heading-like line found in text, or None.

    Scans lines before the first sentence-ending punctuation so we
    don't pick up headings buried inside paragraph text.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Stop scanning once we hit sentence-ending punctuation
        if re.search(r"[.!?]\s*$", stripped):
            break

        for pattern in _HEADING_PATTERNS:
            if pattern.match(stripped):
                return stripped

        # All-uppercase short line (after the numbered/keyword checks)
        if stripped.isupper() and len(stripped) < 60:
            return stripped

    return None


# --- Main enrichment function ------------------------------------------------

def enrich(
    chunks: list[Document],
    document_type: str | None = None,
    product_family: str | None = None,
) -> list[dict]:
    """Convert split Documents into enriched dicts ready for JSONL + ChromaDB.

    Args:
        chunks: output of chunker.split_documents()
        document_type: explicit override; inferred from filename if omitted
        product_family: tag applied to every chunk; "unknown" if omitted

    Returns:
        List of dicts, one per chunk, with all required metadata fields.
    """
    resolved_family = (product_family or "unknown").lower().replace(" ", "_")
    current_heading = "[No Heading]"
    last_source: str | None = None
    result: list[dict] = []
    seq = 0

    for chunk in chunks:
        source_file: str = chunk.metadata.get("source", "unknown")
        raw_page: int = chunk.metadata.get("page", 0)
        page_number: int = raw_page + 1  # PyPDFLoader is 0-indexed

        # Reset sequence counter and heading accumulator when source changes
        if source_file != last_source:
            seq = 0
            current_heading = "[No Heading]"
            last_source = source_file

        resolved_doc_type = (
            document_type
            if document_type is not None
            else _infer_document_type(source_file)
        )

        detected = _detect_heading(chunk.page_content)
        if detected:
            current_heading = detected

        page_str = str(page_number).zfill(3)
        seq_str = str(seq).zfill(3)
        chunk_id = f"{resolved_doc_type}_{resolved_family}_p{page_str}_{seq_str}"
        seq += 1

        text = chunk.page_content
        token_count = len(text.split())

        result.append(
            {
                "chunk_id": chunk_id,
                "text": text,
                "source_file": source_file,
                "page_number": page_number,
                "section_heading": current_heading,
                "document_type": resolved_doc_type,
                "product_family": resolved_family,
                "token_count": token_count,
            }
        )

    _validate_and_log(result)
    return result


def save_chunks(chunks: list[dict], output_path: str) -> Path:
    """Write enriched chunks to a JSONL file under output_path.

    One file per source document, named <source_stem>.jsonl.
    The output directory is created if it does not exist.

    Args:
        chunks: non-empty list of dicts from enrich() — all must share the
                same source_file (call once per source document).
        output_path: directory where the JSONL file will be written.

    Returns:
        Path to the written file.
    """
    if not chunks:
        raise ValueError("save_chunks() requires at least one chunk.")

    source_stem = Path(chunks[0]["source_file"]).stem
    out_dir = Path(output_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{source_stem}.jsonl"

    with out_file.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    logger.info("Saved %d chunk(s) to %s", len(chunks), out_file)
    return out_file


def _validate_and_log(chunks: list[dict]) -> None:
    """Log a summary and warn on any chunks that violate invariants."""
    if not chunks:
        logger.warning("enrich() produced zero chunks.")
        return

    sources = {c["source_file"] for c in chunks}
    token_counts = [c["token_count"] for c in chunks]
    avg_tokens = sum(token_counts) / len(token_counts)

    over_limit = [c for c in chunks if c["token_count"] > 600]
    empty_headings = [c for c in chunks if not c["section_heading"]]

    for source in sorted(sources):
        source_chunks = [c for c in chunks if c["source_file"] == source]
        doc_type = source_chunks[0]["document_type"]
        family = source_chunks[0]["product_family"]
        logger.info(
            "Enriched %d chunk(s) from %s  [type=%s, family=%s]",
            len(source_chunks),
            Path(source).name,
            doc_type,
            family,
        )

    logger.info(
        "Total: %d chunk(s), avg token_count=%.0f",
        len(chunks),
        avg_tokens,
    )

    if over_limit:
        for c in over_limit:
            logger.warning(
                "chunk_id=%s has token_count=%d (>600): source=%s page=%d",
                c["chunk_id"],
                c["token_count"],
                c["source_file"],
                c["page_number"],
            )

    if empty_headings:
        # This should never happen — _detect_heading always falls back to
        # the accumulated heading or "[No Heading]"
        for c in empty_headings:
            logger.error(
                "chunk_id=%s has empty section_heading — this is a bug.",
                c["chunk_id"],
            )
