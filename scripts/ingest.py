"""Ingest PDF documents from a directory into the vector store.

Usage:
    python scripts/ingest.py
    python scripts/ingest.py --path data/raw/manuals/ --doc-type manual --family X200
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # noqa: E402

from app.config import settings  # noqa: E402
from app.embeddings import store  # noqa: E402
from app.embeddings.embedder import embed_texts  # noqa: E402
from app.ingestion.chunker import split_documents  # noqa: E402
from app.ingestion.loader import load_directory  # noqa: E402
from app.ingestion.metadata import enrich, save_chunks  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PDFs into the vector store.")
    parser.add_argument("--path", default=settings.raw_docs_path,
                        help="Directory containing PDF files (default: data/raw/)")
    parser.add_argument("--doc-type", dest="doc_type", default=None,
                        help="Override document type for all files (e.g. manual, datasheet)")
    parser.add_argument("--family", default=None,
                        help="Product family tag applied to all chunks (e.g. X200)")
    args = parser.parse_args()

    logger.info("Loading PDFs from %s …", args.path)
    docs = load_directory(args.path)
    if not docs:
        logger.error("No PDF files found under %s. Aborting.", args.path)
        sys.exit(1)

    # Group pages by source file
    sources: dict[str, list] = {}
    for doc in docs:
        src = doc.metadata.get("source", "unknown")
        sources.setdefault(src, []).append(doc)

    total_chunks = 0
    total_upserted = 0

    for source, pages in sources.items():
        logger.info("Processing %s (%d page(s)) …", Path(source).name, len(pages))
        chunks_docs = split_documents(pages)
        chunks = enrich(chunks_docs, document_type=args.doc_type, product_family=args.family)
        save_chunks(chunks, settings.processed_path)
        embeddings = embed_texts([c["text"] for c in chunks])
        store.upsert_chunks(chunks, embeddings)
        total_chunks += len(chunks)
        total_upserted += len(chunks)

    logger.info(
        "Done. %d file(s) processed, %d chunk(s) created, %d chunk(s) upserted.",
        len(sources),
        total_chunks,
        total_upserted,
    )


if __name__ == "__main__":
    main()
