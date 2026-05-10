"""ChromaDB persistent vector store.

Module-level client and collection are created once on import.
The cosine distance metric is set at collection creation and cannot
be changed later without dropping the collection.
"""

import logging

import chromadb

from app.config import settings

logger = logging.getLogger(__name__)

client = chromadb.PersistentClient(path=settings.embeddings_path)
collection = client.get_or_create_collection(
    name=settings.collection_name,
    metadata={"hnsw:space": "cosine"},
)


def upsert_chunks(chunks: list[dict], embeddings: list[list[float]]) -> None:
    """Upsert enriched chunk dicts and their embedding vectors into ChromaDB."""
    collection.upsert(
        ids=[c["chunk_id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        embeddings=embeddings,
        metadatas=[
            {
                "source_file": c["source_file"],
                "page_number": c["page_number"],
                "section_heading": c["section_heading"],
                "document_type": c["document_type"],
                "product_family": c["product_family"],
            }
            for c in chunks
        ],
    )
    logger.info("Upserted %d chunk(s) into collection '%s'", len(chunks), settings.collection_name)


def query(
    embedding: list[float],
    top_k: int,
    filter: dict | None = None,
) -> list[dict]:
    """Query the collection and return the top-k results.

    Args:
        embedding: query vector from embed_texts()
        top_k: number of results to return
        filter: optional ChromaDB `where` clause (e.g. {"product_family": "x200"})

    Returns:
        List of dicts with keys: text, score, source_file, page_number,
        section_heading, document_type, product_family.
    """
    results = collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
        where=filter,
        include=["documents", "distances", "metadatas"],
    )

    docs = results["documents"][0]
    distances = results["distances"][0]
    metadatas = results["metadatas"][0]

    return [
        {
            "text": doc,
            "score": 1.0 - dist,  # cosine distance → similarity
            **meta,
        }
        for doc, dist, meta in zip(docs, distances, metadatas)
    ]
