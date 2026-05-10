"""Tests for Step 5: retriever.

Unit tests mock embedder and store so they run offline.
Integration tests (pytest.mark.integration) require Ollama + nomic-embed-text.
"""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_FAKE_VECTOR = [0.1] * 768

_SAMPLE_RESULT = {
    "text": "Motor must be calibrated before use.",
    "score": 0.91,
    "source_file": "data/raw/X200_manual.pdf",
    "page_number": 3,
    "section_heading": "3.2 Motor Calibration",
    "document_type": "manual",
    "product_family": "x200",
}


def _make_results(n: int = 3) -> list[dict]:
    return [dict(_SAMPLE_RESULT, score=0.9 - i * 0.05, page_number=i + 1) for i in range(n)]


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestRetrieveUnit:
    def _patch(self, embed_return=None, query_return=None):
        embed_return = embed_return or [_FAKE_VECTOR]
        query_return = query_return if query_return is not None else _make_results(3)
        embed_mock = MagicMock(return_value=embed_return)
        query_mock = MagicMock(return_value=query_return)
        return (
            patch("app.retrieval.retriever.embedder.embed_texts", embed_mock),
            patch("app.retrieval.retriever.store.query", query_mock),
            embed_mock,
            query_mock,
        )

    def test_returns_list(self):
        p_embed, p_query, _, _ = self._patch()
        with p_embed, p_query:
            from app.retrieval.retriever import retrieve
            result = retrieve("test query")
        assert isinstance(result, list)

    def test_returns_top_k_results(self):
        p_embed, p_query, _, _ = self._patch(query_return=_make_results(5))
        with p_embed, p_query:
            from app.retrieval.retriever import retrieve
            result = retrieve("test query", top_k=5)
        assert len(result) == 5

    def test_embeds_query_text(self):
        p_embed, p_query, embed_mock, _ = self._patch()
        with p_embed, p_query:
            from app.retrieval.retriever import retrieve
            retrieve("motor calibration")
        embed_mock.assert_called_once_with(["motor calibration"])

    def test_passes_embedding_to_store(self):
        vec = [0.5] * 768
        p_embed, p_query, _, query_mock = self._patch(embed_return=[vec])
        with p_embed, p_query:
            from app.retrieval.retriever import retrieve
            retrieve("test query", top_k=3)
        call_args = query_mock.call_args
        assert call_args[0][0] == vec
        assert call_args[0][1] == 3

    def test_no_filter_when_product_family_none(self):
        p_embed, p_query, _, query_mock = self._patch()
        with p_embed, p_query:
            from app.retrieval.retriever import retrieve
            retrieve("test query")
        assert query_mock.call_args[0][2] is None

    def test_filter_passed_when_product_family_given(self):
        p_embed, p_query, _, query_mock = self._patch()
        with p_embed, p_query:
            from app.retrieval.retriever import retrieve
            retrieve("test query", product_family="x200")
        assert query_mock.call_args[0][2] == {"product_family": "x200"}

    def test_result_schema(self):
        p_embed, p_query, _, _ = self._patch(query_return=[_SAMPLE_RESULT])
        with p_embed, p_query:
            from app.retrieval.retriever import retrieve
            result = retrieve("test query", top_k=1)
        required = {"text", "score", "source_file", "page_number", "section_heading",
                    "document_type", "product_family"}
        assert required.issubset(result[0].keys())

    def test_empty_result_from_store(self):
        p_embed, p_query, _, _ = self._patch(query_return=[])
        with p_embed, p_query:
            from app.retrieval.retriever import retrieve
            result = retrieve("test query")
        assert result == []

    def test_default_top_k_from_settings(self):
        from app.config import settings
        p_embed, p_query, _, query_mock = self._patch()
        with p_embed, p_query:
            from app.retrieval.retriever import retrieve
            retrieve("test query")
        assert query_mock.call_args[0][1] == settings.top_k


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
class TestRetrieveIntegration:
    def _populated_collection(self):
        """Return a temporary in-memory ChromaDB collection with 3 embedded chunks."""
        import chromadb

        from app.embeddings.embedder import embed_texts

        texts = [
            "Motor calibration procedure: set speed to 1500 RPM.",
            "Safety warnings: always wear protective equipment before operation.",
            "Spare parts list: refer to appendix B for part numbers.",
        ]
        chunks = [
            {
                "chunk_id": f"manual_x200_p00{i+1}_000",
                "text": t,
                "source_file": "data/raw/X200_manual.pdf",
                "page_number": i + 1,
                "section_heading": f"Section {i+1}",
                "document_type": "manual",
                "product_family": "x200",
                "token_count": len(t.split()),
            }
            for i, t in enumerate(texts)
        ]
        vecs = embed_texts(texts)
        col = chromadb.EphemeralClient().get_or_create_collection(
            name="integration_retrieval",
            metadata={"hnsw:space": "cosine"},
        )
        col.upsert(
            ids=[c["chunk_id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            embeddings=vecs,
            metadatas=[
                {k: c[k] for k in ("source_file", "page_number", "section_heading",
                                    "document_type", "product_family")}
                for c in chunks
            ],
        )
        return col

    def test_relevant_chunk_is_top_result(self):
        col = self._populated_collection()
        with patch("app.retrieval.retriever.store.collection", col):
            from app.retrieval.retriever import retrieve
            results = retrieve("How do I calibrate the motor?", top_k=3)
        assert len(results) > 0
        assert "calibration" in results[0]["text"].lower()

    def test_top_k_respected(self):
        col = self._populated_collection()
        with patch("app.retrieval.retriever.store.collection", col):
            from app.retrieval.retriever import retrieve
            results = retrieve("equipment operation", top_k=2)
        assert len(results) == 2

    def test_scores_descending(self):
        col = self._populated_collection()
        with patch("app.retrieval.retriever.store.collection", col):
            from app.retrieval.retriever import retrieve
            results = retrieve("motor calibration procedure", top_k=3)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)
