"""Split LangChain Documents into overlapping text chunks.

chunk_size and chunk_overlap are in characters, not tokens.
1500 characters ≈ 300–400 tokens for English technical text, which fits
within nomic-embed-text's 512-token context window.

RecursiveCharacterTextSplitter preserves source/page metadata on each chunk.
"""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings


def split_documents(documents: list[Document]) -> list[Document]:
    """Split Documents into overlapping chunks using chunk_size/chunk_overlap from settings."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " "],
    )
    return splitter.split_documents(documents)
