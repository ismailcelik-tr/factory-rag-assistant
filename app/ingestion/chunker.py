"""Split LangChain Documents into overlapping text chunks.

chunk_size and chunk_overlap are in characters, not tokens.
1500 characters ≈ 300–400 tokens for English technical text, which fits
within nomic-embed-text's 512-token context window.

RecursiveCharacterTextSplitter preserves source/page metadata on each chunk.
"""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " "],
)


def split_documents(documents: list[Document]) -> list[Document]:
    """Split a list of Documents into ~1500-character chunks with 200-char overlap.

    Source file path and page number from each Document's metadata are
    preserved on every output chunk automatically.
    """
    return _splitter.split_documents(documents)
