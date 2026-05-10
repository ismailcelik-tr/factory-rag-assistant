"""Load PDF documents from disk using PyMuPDF (fitz).

Returns one LangChain Document per page. Each Document carries:
  - page_content: extracted plain text
  - metadata["source"]: path to the source file
  - metadata["page"]: 0-indexed page number (add 1 in the metadata step)

PyMuPDF is used instead of PyPDFLoader because it produces clean, properly
spaced text for PDFs that use character-spaced fonts — a common issue with
documents exported from certain design tools.
"""

import logging
from pathlib import Path

import fitz  # pymupdf
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def load_pdf(path: str) -> list[Document]:
    """Load a single PDF file and return one Document per page."""
    docs: list[Document] = []
    pdf = fitz.open(path)

    for page_num, page in enumerate(pdf):
        text = page.get_text()
        if text.strip():
            docs.append(
                Document(
                    page_content=text,
                    metadata={"source": path, "page": page_num},
                )
            )

    pdf.close()

    if not docs:
        logger.warning(
            "No text extracted from %s — file may be a scanned PDF (no text layer).",
            path,
        )

    logger.debug("Loaded %d page(s) from %s", len(docs), path)
    return docs


def load_directory(path: str) -> list[Document]:
    """Load all PDF files found recursively under path."""
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
