"""Tests for Step 4: embedder and vector store.

Unit tests (no Ollama required): mock the embedding model and a temporary
ChromaDB collection to verify upsert/query logic in isolation.

Integration tests (require Ollama): marked with pytest.mark.integration.
Run with:  pytest app/tests/test_embeddings.py -m integration -v
Skip with: pytest app/tests/test_embeddings.py -m "not integration" -v
"""

import pytest

# ---------------------------------------------------------------------------
# Unit tests — no Ollama, no real ChromaDB on disk
# ---------------------------------------------------------------------------


class TestUpsertAndQueryUnit:
    """Exercise store logic using an in-memory ChromaDB collection."""

    def _make_collection(self):
        import uuid

        import chromadb

        # Unique name per call so EphemeralClient instances don't share state
        client = chromadb.EphemeralClient()
        return client.get_or_create_collection(
            name=f"test_{uuid.uuid4().hex}",
            metadata={"hnsw:space": "cosine"},
        )

    def _make_chunks(self, n: int = 3, source: str = "data/raw/manual.pdf") -> list[dict]:
        return [
            {
                "chunk_id": f"manual_unknown_p001_{i:03d}",
                "text": f"Content block {i}.",
                "source_file": source,
                "page_number": 1,
                "section_heading": "Introduction",
                "document_type": "manual",
                "product_family": "unknown",
                "token_count": 3,
            }
            for i in range(n)
        ]

    def _fake_vectors(self, n: int, dim: int = 8) -> list[list[float]]:
        import math

        return [
            [math.sin(i + j * 0.1) for j in range(dim)]
            for i in range(n)
        ]

    def test_upsert_and_count(self):
        from unittest.mock import patch

        col = self._make_collection()
        chunks = self._make_chunks(3)
        vecs = self._fake_vectors(3)

        with patch("app.embeddings.store.collection", col):
            from app.embeddings.store import upsert_chunks

            upsert_chunks(chunks, vecs)

        assert col.count() == 3

    def test_upsert_idempotent(self):
        from unittest.mock import patch

        col = self._make_collection()
        chunks = self._make_chunks(2)
        vecs = self._fake_vectors(2)

        with patch("app.embeddings.store.collection", col):
            from app.embeddings.store import upsert_chunks

            upsert_chunks(chunks, vecs)
            upsert_chunks(chunks, vecs)  # same ids → upsert, not duplicate

        assert col.count() == 2

    def test_query_returns_top_k(self):
        from unittest.mock import patch

        col = self._make_collection()
        chunks = self._make_chunks(5)
        vecs = self._fake_vectors(5)

        col.upsert(
            ids=[c["chunk_id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            embeddings=vecs,
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

        with patch("app.embeddings.store.collection", col):
            from app.embeddings.store import query

            results = query(vecs[0], top_k=3)

        assert len(results) == 3

    def test_query_result_schema(self):
        from unittest.mock import patch

        col = self._make_collection()
        chunks = self._make_chunks(2)
        vecs = self._fake_vectors(2)

        col.upsert(
            ids=[c["chunk_id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            embeddings=vecs,
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

        with patch("app.embeddings.store.collection", col):
            from app.embeddings.store import query

            results = query(vecs[0], top_k=1)

        required = {"text", "score", "source_file", "page_number", "section_heading",
                    "document_type", "product_family"}
        assert required.issubset(results[0].keys())

    def test_query_score_in_range(self):
        from unittest.mock import patch

        col = self._make_collection()
        chunks = self._make_chunks(2)
        vecs = self._fake_vectors(2)

        col.upsert(
            ids=[c["chunk_id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            embeddings=vecs,
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

        with patch("app.embeddings.store.collection", col):
            from app.embeddings.store import query

            results = query(vecs[0], top_k=2)

        for r in results:
            assert -1.01 <= r["score"] <= 1.01  # allow float rounding past ±1.0

    def test_query_with_filter(self):
        from unittest.mock import patch

        col = self._make_collection()
        chunks_a = self._make_chunks(2, source="data/raw/doc_a.pdf")
        chunks_b = self._make_chunks(2, source="data/raw/doc_b.pdf")
        for c in chunks_b:
            c["chunk_id"] = c["chunk_id"] + "_b"
            c["product_family"] = "x200"

        all_chunks = chunks_a + chunks_b
        vecs = self._fake_vectors(4)

        col.upsert(
            ids=[c["chunk_id"] for c in all_chunks],
            documents=[c["text"] for c in all_chunks],
            embeddings=vecs,
            metadatas=[
                {
                    "source_file": c["source_file"],
                    "page_number": c["page_number"],
                    "section_heading": c["section_heading"],
                    "document_type": c["document_type"],
                    "product_family": c["product_family"],
                }
                for c in all_chunks
            ],
        )

        with patch("app.embeddings.store.collection", col):
            from app.embeddings.store import query

            results = query(vecs[0], top_k=4, filter={"product_family": "x200"})

        assert all(r["product_family"] == "x200" for r in results)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Integration tests — require Ollama running with nomic-embed-text pulled
# ---------------------------------------------------------------------------


def _ollama_available() -> bool:
    try:
        import httpx

        r = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


_skip_if_no_ollama = pytest.mark.skipif(
    not _ollama_available(),
    reason="Ollama not running — skipping integration tests",
)


@_skip_if_no_ollama
class TestEmbedderIntegration:
    def test_embed_returns_vectors(self):
        from app.embeddings.embedder import embed_texts

        vecs = embed_texts(["motor calibration procedure"])
        assert len(vecs) == 1
        assert isinstance(vecs[0], list)

    def test_vector_dimension_is_768(self):
        from app.embeddings.embedder import embed_texts

        vecs = embed_texts(["test string"])
        assert len(vecs[0]) == 768

    def test_embed_multiple_texts(self):
        from app.embeddings.embedder import embed_texts

        texts = ["motor calibration", "safety warnings", "installation steps"]
        vecs = embed_texts(texts)
        assert len(vecs) == 3
        assert all(len(v) == 768 for v in vecs)

    def test_similar_texts_have_higher_score_than_dissimilar(self):
        import math

        from app.embeddings.embedder import embed_texts

        texts = [
            "motor calibration procedure",
            "motor calibration steps",
            "invoice payment terms",
        ]
        vecs = embed_texts(texts)
        v_query, v_similar, v_dissimilar = vecs[0], vecs[1], vecs[2]

        def cosine(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(x * x for x in b))
            return dot / (na * nb)

        assert cosine(v_query, v_similar) > cosine(v_query, v_dissimilar)


@_skip_if_no_ollama
class TestStoreIntegration:
    def test_upsert_and_query_roundtrip(self):
        import chromadb

        from app.embeddings.embedder import embed_texts

        col = chromadb.EphemeralClient().get_or_create_collection(
            name="integration_test",
            metadata={"hnsw:space": "cosine"},
        )

        texts = [
            "motor calibration procedure",
            "safety warnings before operation",
            "spare parts list",
        ]
        vecs = embed_texts(texts)
        chunks = [
            {
                "chunk_id": f"manual_unknown_p001_{i:03d}",
                "text": t,
                "source_file": "data/raw/manual.pdf",
                "page_number": i + 1,
                "section_heading": "Test Section",
                "document_type": "manual",
                "product_family": "unknown",
                "token_count": len(t.split()),
            }
            for i, t in enumerate(texts)
        ]

        from unittest.mock import patch

        with patch("app.embeddings.store.collection", col):
            from app.embeddings.store import query, upsert_chunks

            upsert_chunks(chunks, vecs)
            query_vec = embed_texts(["motor calibration"])[0]
            results = query(query_vec, top_k=1)

        assert len(results) == 1
        assert "motor calibration" in results[0]["text"].lower()
