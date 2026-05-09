"""Load PDF documents from disk using LangChain's PyPDFLoader.

Returns one LangChain Document per page. Each Document carries:
  - page_content: extracted plain text
  - metadata["source"]: path to the source file as passed to PyPDFLoader
  - metadata["page"]: 0-indexed page number (add 1 in the metadata step)
"""

import logging
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def load_pdf(path: str) -> list[Document]:
    """Load a single PDF file and return one Document per page.

    Returns an empty list if the file yields no text (e.g. scanned PDF).
    """
    docs: list[Document] = PyPDFLoader(path).load()

    if all(not doc.page_content.strip() for doc in docs):
        logger.warning(
            "No text extracted from %s — file may be a scanned PDF (no text layer).",
            path,
        )
        return []

    logger.debug("Loaded %d page(s) from %s", len(docs), path)
    return docs


def load_directory(path: str) -> list[Document]:
    """Load all PDF files found recursively under path.

    Files that yield no text are skipped with a warning.
    Returns all pages from all valid PDFs, in filesystem order.
    """
    pdf_paths = sorted(Path(path).rglob("*.pdf"))

    if not pdf_paths:
        logger.warning("No PDF files found under %s", path)
        return []

    documents: list[Document] = []
    loaded_count = 0

    for pdf_path in pdf_paths:
        docs = load_pdf(str(pdf_path))
        if docs:
            documents.extend(docs)
            loaded_count += 1

    logger.info(
        "Loaded %d page(s) from %d/%d PDF(s) under %s",
        len(documents),
        loaded_count,
        len(pdf_paths),
        path,
    )
    return documents
