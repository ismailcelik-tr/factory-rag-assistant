"""Retrieve the top-k chunks most relevant to a query string.

Coordinates the embedder and vector store: embeds the query, applies an
optional product_family filter, and returns ranked chunks with metadata.
"""

from app.config import settings
from app.embeddings import embedder, store


def retrieve(
    query: str,
    top_k: int = settings.top_k,
    product_family: str | None = None,
) -> list[dict]:
    """Return the top-k chunks most relevant to query.

    Args:
        query: natural-language question from the user
        top_k: number of results to return (defaults to settings.top_k)
        product_family: if provided, restricts results to chunks from this
                        family (must match the value stored in ChromaDB)

    Returns:
        List of dicts ordered by descending similarity score, each with:
        text, score, source_file, page_number, section_heading,
        document_type, product_family.
    """
    embedding = embedder.embed_texts([query])[0]
    filter_ = {"product_family": product_family} if product_family is not None else None
    return store.query(embedding, top_k, filter_)
