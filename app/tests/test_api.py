"""Tests for Step 9: FastAPI routes.

All external calls (retriever, OllamaProvider, store, embedder, loader)
are mocked so these tests run fully offline.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_CHUNK = {
    "text": "The motor calibration speed is 1500 RPM.",
    "score": 0.92,
    "source_file": "data/raw/X200_manual.pdf",
    "page_number": 3,
    "section_heading": "3.2 Motor Calibration",
    "document_type": "manual",
    "product_family": "x200",
}

_ASK_PAYLOAD = {
    "query": "What is the motor calibration speed?",
    "role": "tech_service",
}


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_returns_200(self):
        with (
            patch("app.api.routes.httpx.get") as mock_get,
            patch("app.api.routes.store.collection") as mock_col,
        ):
            mock_get.return_value = MagicMock(status_code=200)
            mock_col.count.return_value = 42
            response = client.get("/api/health")
        assert response.status_code == 200

    def test_ok_when_ollama_reachable(self):
        with (
            patch("app.api.routes.httpx.get") as mock_get,
            patch("app.api.routes.store.collection") as mock_col,
        ):
            mock_get.return_value = MagicMock(status_code=200)
            mock_col.count.return_value = 0
            data = client.get("/api/health").json()
        assert data["ollama"] == "reachable"
        assert data["status"] == "ok"

    def test_degraded_when_ollama_unreachable(self):
        with (
            patch("app.api.routes.httpx.get", side_effect=Exception("connection refused")),
            patch("app.api.routes.store.collection") as mock_col,
        ):
            mock_col.count.return_value = 0
            data = client.get("/api/health").json()
        assert data["ollama"] == "unreachable"
        assert data["status"] == "degraded"

    def test_chunks_indexed_returned(self):
        with (
            patch("app.api.routes.httpx.get") as mock_get,
            patch("app.api.routes.store.collection") as mock_col,
        ):
            mock_get.return_value = MagicMock(status_code=200)
            mock_col.count.return_value = 123
            data = client.get("/api/health").json()
        assert data["chunks_indexed"] == 123


# ---------------------------------------------------------------------------
# POST /api/ask
# ---------------------------------------------------------------------------


class TestAsk:
    def _mock_ask(self, chunks=None, llm_response="The speed is 1500 RPM."):
        if chunks is None:
            chunks = [_CHUNK]
        return (
            patch("app.api.routes.retrieve", return_value=chunks),
            patch("app.api.routes.OllamaProvider.generate", return_value=llm_response),
        )

    def test_returns_200(self):
        p_ret, p_llm = self._mock_ask()
        with p_ret, p_llm:
            response = client.post("/api/ask", json=_ASK_PAYLOAD)
        assert response.status_code == 200

    def test_response_schema(self):
        p_ret, p_llm = self._mock_ask()
        with p_ret, p_llm:
            data = client.post("/api/ask", json=_ASK_PAYLOAD).json()
        required = {"answer", "citations", "role", "model", "chunks_used"}
        assert required.issubset(data.keys())

    def test_answer_contains_llm_response(self):
        p_ret, p_llm = self._mock_ask(llm_response="Speed is 1500 RPM.")
        with p_ret, p_llm:
            data = client.post("/api/ask", json=_ASK_PAYLOAD).json()
        assert data["answer"] == "Speed is 1500 RPM."

    def test_role_echoed_in_response(self):
        p_ret, p_llm = self._mock_ask()
        with p_ret, p_llm:
            data = client.post("/api/ask", json=_ASK_PAYLOAD).json()
        assert data["role"] == "tech_service"

    def test_chunks_used_count(self):
        p_ret, p_llm = self._mock_ask(chunks=[_CHUNK, _CHUNK])
        with p_ret, p_llm:
            data = client.post("/api/ask", json=_ASK_PAYLOAD).json()
        assert data["chunks_used"] == 2

    def test_no_results_when_empty_chunks(self):
        p_ret, p_llm = self._mock_ask(chunks=[])
        with p_ret, p_llm:
            data = client.post("/api/ask", json=_ASK_PAYLOAD).json()
        assert data["no_results"] is True
        assert data["answer"] is None
        assert data["citations"] == []

    def test_citation_fallback_when_no_cite_markers(self):
        # LLM returns text with no [cite: ...] markers
        p_ret, p_llm = self._mock_ask(llm_response="The speed is 1500 RPM.")
        with p_ret, p_llm:
            data = client.post("/api/ask", json=_ASK_PAYLOAD).json()
        # Fallback builds citations from context chunks
        assert len(data["citations"]) == 1
        assert data["citations"][0]["source_file"] == "X200_manual.pdf"

    def test_citations_parsed_from_llm_output(self):
        llm_out = (
            'Speed is 1500 RPM [cite: X200_manual.pdf, p.3, "3.2 Motor Calibration"].'
        )
        p_ret, p_llm = self._mock_ask(llm_response=llm_out)
        with p_ret, p_llm:
            data = client.post("/api/ask", json=_ASK_PAYLOAD).json()
        assert data["citations"][0]["source_file"] == "X200_manual.pdf"
        assert data["citations"][0]["page_number"] == 3

    def test_invalid_role_returns_422(self):
        response = client.post("/api/ask", json={"query": "test", "role": "ghost"})
        assert response.status_code == 422

    def test_empty_query_returns_422(self):
        response = client.post("/api/ask", json={"query": "", "role": "tech_service"})
        assert response.status_code == 422

    def test_product_family_passed_to_retriever(self):
        with patch("app.api.routes.retrieve", return_value=[]) as mock_ret:
            with patch("app.api.routes.OllamaProvider.generate", return_value="ok"):
                client.post(
                    "/api/ask",
                    json={**_ASK_PAYLOAD, "product_family": "X200"},
                )
        assert mock_ret.call_args[1]["product_family"] == "X200"


# ---------------------------------------------------------------------------
# POST /api/ingest
# ---------------------------------------------------------------------------


class TestIngest:
    def _mock_ingest(self, docs=None):
        from langchain_core.documents import Document

        if docs is None:
            docs = [Document(
                page_content="Content.",
                metadata={"source": "data/raw/manual.pdf", "page": 0},
            )]
        return (
            patch("app.api.routes.load_directory", return_value=docs),
            patch("app.api.routes.embed_texts", return_value=[[0.1] * 768]),
            patch("app.api.routes.store.upsert_chunks"),
        )

    def test_returns_200(self):
        p_load, p_embed, p_upsert = self._mock_ingest()
        with p_load, p_embed, p_upsert:
            response = client.post("/api/ingest", json={})
        assert response.status_code == 200

    def test_response_schema(self):
        p_load, p_embed, p_upsert = self._mock_ingest()
        with p_load, p_embed, p_upsert:
            data = client.post("/api/ingest", json={}).json()
        required = {"files_processed", "chunks_created", "chunks_upserted", "errors"}
        assert required.issubset(data.keys())

    def test_files_processed_count(self):
        p_load, p_embed, p_upsert = self._mock_ingest()
        with p_load, p_embed, p_upsert:
            data = client.post("/api/ingest", json={}).json()
        assert data["files_processed"] == 1

    def test_no_pdfs_returns_error(self):
        with patch("app.api.routes.load_directory", return_value=[]):
            data = client.post("/api/ingest", json={}).json()
        assert data["files_processed"] == 0
        assert len(data["errors"]) == 1

    def test_chunks_created_positive(self):
        p_load, p_embed, p_upsert = self._mock_ingest()
        with p_load, p_embed, p_upsert:
            data = client.post("/api/ingest", json={}).json()
        assert data["chunks_created"] > 0
