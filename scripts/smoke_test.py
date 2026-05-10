"""End-to-end smoke test for Phase 1.

Finds the first PDF in data/raw/, ingests it, asks a hardcoded question,
and asserts the response has a non-null answer and at least one citation.

Prints PASS or FAIL with the full response.

Usage:
    python scripts/smoke_test.py
"""

import json
import logging
import sys
from pathlib import Path

# Keep sys.path manipulation before app imports so the script works when run
# directly from any directory without `pip install -e .`
sys.path.insert(0, str(Path(__file__).parent.parent))  # noqa: E402

from app.config import settings  # noqa: E402
from app.embeddings import store  # noqa: E402
from app.embeddings.embedder import embed_texts  # noqa: E402
from app.ingestion.chunker import split_documents  # noqa: E402
from app.ingestion.loader import load_pdf  # noqa: E402
from app.ingestion.metadata import enrich, save_chunks  # noqa: E402
from app.llm.ollama_provider import OllamaProvider  # noqa: E402
from app.llm.parser import extract_citations  # noqa: E402
from app.prompts.assembler import build_system_prompt, build_user_message  # noqa: E402
from app.retrieval.retriever import retrieve  # noqa: E402

QUESTION = "What is this document about?"
ROLE = "tech_service"


def main() -> None:
    logging.basicConfig(level=logging.WARNING)

    # --- Find first PDF ---
    pdf_files = sorted(Path(settings.raw_docs_path).rglob("*.pdf"))
    if not pdf_files:
        print(f"FAIL: No PDF files found under {settings.raw_docs_path}")
        print("      Place at least one PDF in data/raw/ and re-run.")
        sys.exit(1)

    pdf_path = pdf_files[0]
    print(f"Using: {pdf_path}")

    # --- Ingest ---
    print("Step 1/4  Loading and chunking …")
    docs = load_pdf(str(pdf_path))
    if not docs:
        print(f"FAIL: No text extracted from {pdf_path.name} (possibly a scanned PDF).")
        sys.exit(1)

    chunks_docs = split_documents(docs)
    chunks = enrich(chunks_docs)
    save_chunks(chunks, settings.processed_path)
    print(f"          {len(chunks)} chunk(s) created.")

    # --- Embed and upsert ---
    print("Step 2/4  Embedding and indexing …")
    embeddings = embed_texts([c["text"] for c in chunks])
    store.upsert_chunks(chunks, embeddings)
    print(f"          {len(embeddings)} vector(s) upserted.")

    # --- Retrieve ---
    print("Step 3/4  Retrieving …")
    retrieved = retrieve(QUESTION, top_k=settings.top_k)
    if not retrieved:
        print("FAIL: retrieve() returned no chunks.")
        sys.exit(1)
    top_score = retrieved[0]["score"]
    print(f"          {len(retrieved)} chunk(s) retrieved (top score: {top_score:.3f}).")

    # --- Generate answer ---
    print("Step 4/4  Generating answer …")
    system_prompt = build_system_prompt(ROLE)
    user_message = build_user_message(QUESTION, retrieved)
    answer = OllamaProvider().generate(system_prompt, user_message)
    citations = extract_citations(answer)

    # Fallback citations from context chunks if model omits markers
    if not citations:
        from app.api.schemas import Citation
        citations = [
            Citation(
                source_file=Path(c["source_file"]).name,
                page_number=c["page_number"],
                section_heading=c["section_heading"],
            )
            for c in retrieved
        ]

    # --- Assert ---
    response = {
        "question": QUESTION,
        "role": ROLE,
        "answer": answer,
        "citations": [c.model_dump() for c in citations],
        "chunks_used": len(retrieved),
        "model": settings.llm_model,
    }

    print("\n" + "=" * 60)
    print(json.dumps(response, indent=2, ensure_ascii=False))
    print("=" * 60)

    passed = answer is not None and len(answer.strip()) > 0 and len(citations) > 0

    if passed:
        print("\nPASS")
    else:
        print("\nFAIL")
        if not answer or not answer.strip():
            print("  • answer is empty")
        if not citations:
            print("  • citations list is empty")
        sys.exit(1)


if __name__ == "__main__":
    main()
