"""Embed text using nomic-embed-text via Ollama.

Returns raw float vectors; does not interact with ChromaDB directly.
"""

from langchain_ollama import OllamaEmbeddings

from app.config import settings

_model = OllamaEmbeddings(
    model=settings.embedding_model,
    base_url=settings.ollama_base_url,
)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings and return one vector per string."""
    return _model.embed_documents(texts)
