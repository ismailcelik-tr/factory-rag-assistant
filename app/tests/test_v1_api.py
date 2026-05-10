"""Tests for Phase 2: /api/v1/ routes.

All external calls are mocked — runs fully offline.
Mock targets use 'app.api.v1.routes.*' prefix (not 'app.api.routes.*').
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
# GET /api/v1/health
# ---------------------------------------------------------------------------


class TestV1Health:
    def test_returns_200(self):
        with (
            patch("app.api.v1.routes.httpx.get") as mock_get,
            patch("app.api.v1.routes.store.collection") as mock_col,
        ):
            mock_get.return_value = MagicMock(status_code=200)
            mock_col.count.return_value = 0
            response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_ok_when_ollama_reachable(self):
        with (
            patch("app.api.v1.routes.httpx.get") as mock_get,
            patch("app.api.v1.routes.store.collection") as mock_col,
        ):
            mock_get.return_value = MagicMock(status_code=200)
            mock_col.count.return_value = 0
            data = client.get("/api/v1/health").json()
        assert data["ollama"] == "reachable"
        assert data["status"] == "ok"

    def test_degraded_when_ollama_unreachable(self):
        with (
            patch("app.api.v1.routes.httpx.get", side_effect=Exception("refused")),
            patch("app.api.v1.routes.store.collection") as mock_col,
        ):
            mock_col.count.return_value = 0
            data = client.get("/api/v1/health").json()
        assert data["ollama"] == "unreachable"
        assert data["status"] == "degraded"

    def test_chunks_indexed_returned(self):
        with (
            patch("app.api.v1.routes.httpx.get") as mock_get,
            patch("app.api.v1.routes.store.collection") as mock_col,
        ):
            mock_get.return_value = MagicMock(status_code=200)
            mock_col.count.return_value = 99
            data = client.get("/api/v1/health").json()
        assert data["chunks_indexed"] == 99


# ---------------------------------------------------------------------------
# GET /api/v1/roles
# ---------------------------------------------------------------------------


class TestV1Roles:
    def test_returns_200(self):
        assert client.get("/api/v1/roles").status_code == 200

    def test_returns_roles_key(self):
        data = client.get("/api/v1/roles").json()
        assert "roles" in data

    def test_all_six_roles_present(self):
        from app.api.schemas import Role

        data = client.get("/api/v1/roles").json()
        expected = {r.value for r in Role}
        assert expected == set(data["roles"])

    def test_roles_are_strings(self):
        data = client.get("/api/v1/roles").json()
        assert all(isinstance(r, str) for r in data["roles"])


# ---------------------------------------------------------------------------
# POST /api/v1/ask
# ---------------------------------------------------------------------------


class TestV1Ask:
    def _mock_ask(self, chunks=None, llm_response="The speed is 1500 RPM."):
        if chunks is None:
            chunks = [_CHUNK]
        return (
            patch("app.api.v1.routes.retrieve", return_value=chunks),
            patch("app.api.v1.routes.OllamaProvider.generate", return_value=llm_response),
        )

    def test_returns_200(self):
        p_ret, p_llm = self._mock_ask()
        with p_ret, p_llm:
            assert client.post("/api/v1/ask", json=_ASK_PAYLOAD).status_code == 200

    def test_response_schema(self):
        p_ret, p_llm = self._mock_ask()
        with p_ret, p_llm:
            data = client.post("/api/v1/ask", json=_ASK_PAYLOAD).json()
        assert {"answer", "citations", "role", "model", "chunks_used"}.issubset(data.keys())

    def test_session_id_accepted(self):
        p_ret, p_llm = self._mock_ask()
        with p_ret, p_llm:
            response = client.post(
                "/api/v1/ask",
                json={**_ASK_PAYLOAD, "session_id": "abc-123"},
            )
        assert response.status_code == 200

    def test_session_id_optional(self):
        p_ret, p_llm = self._mock_ask()
        with p_ret, p_llm:
            assert client.post("/api/v1/ask", json=_ASK_PAYLOAD).status_code == 200

    def test_answer_contains_llm_response(self):
        p_ret, p_llm = self._mock_ask(llm_response="Speed is 1500 RPM.")
        with p_ret, p_llm:
            data = client.post("/api/v1/ask", json=_ASK_PAYLOAD).json()
        assert data["answer"] == "Speed is 1500 RPM."

    def test_role_echoed_in_response(self):
        p_ret, p_llm = self._mock_ask()
        with p_ret, p_llm:
            data = client.post("/api/v1/ask", json=_ASK_PAYLOAD).json()
        assert data["role"] == "tech_service"

    def test_chunks_used_count(self):
        p_ret, p_llm = self._mock_ask(chunks=[_CHUNK, _CHUNK])
        with p_ret, p_llm:
            data = client.post("/api/v1/ask", json=_ASK_PAYLOAD).json()
        assert data["chunks_used"] == 2

    def test_no_results_when_empty_chunks(self):
        p_ret, p_llm = self._mock_ask(chunks=[])
        with p_ret, p_llm:
            data = client.post("/api/v1/ask", json=_ASK_PAYLOAD).json()
        assert data["no_results"] is True
        assert data["answer"] is None
        assert data["citations"] == []

    def test_citation_fallback_when_no_cite_markers(self):
        p_ret, p_llm = self._mock_ask(llm_response="The speed is 1500 RPM.")
        with p_ret, p_llm:
            data = client.post("/api/v1/ask", json=_ASK_PAYLOAD).json()
        assert len(data["citations"]) == 1
        assert data["citations"][0]["source_file"] == "X200_manual.pdf"

    def test_citations_parsed_from_llm_output(self):
        llm_out = 'Speed is 1500 RPM [cite: X200_manual.pdf, p.3, "3.2 Motor Calibration"].'
        p_ret, p_llm = self._mock_ask(llm_response=llm_out)
        with p_ret, p_llm:
            data = client.post("/api/v1/ask", json=_ASK_PAYLOAD).json()
        assert data["citations"][0]["source_file"] == "X200_manual.pdf"
        assert data["citations"][0]["page_number"] == 3

    def test_invalid_role_returns_422(self):
        response = client.post("/api/v1/ask", json={"query": "test", "role": "ghost"})
        assert response.status_code == 422

    def test_422_response_has_error_and_code_fields(self):
        data = client.post("/api/v1/ask", json={"query": "test", "role": "ghost"}).json()
        assert "error" in data
        assert "code" in data
        assert data["code"] == "validation_error"

    def test_empty_query_returns_422(self):
        response = client.post("/api/v1/ask", json={"query": "", "role": "tech_service"})
        assert response.status_code == 422

    def test_product_family_passed_to_retriever(self):
        with patch("app.api.v1.routes.retrieve", return_value=[]) as mock_ret:
            with patch("app.api.v1.routes.OllamaProvider.generate", return_value="ok"):
                client.post("/api/v1/ask", json={**_ASK_PAYLOAD, "product_family": "X200"})
        assert mock_ret.call_args[1]["product_family"] == "X200"

    def test_chunks_retrieved_header_set(self):
        p_ret, p_llm = self._mock_ask(chunks=[_CHUNK, _CHUNK])
        with p_ret, p_llm:
            response = client.post("/api/v1/ask", json=_ASK_PAYLOAD)
        assert "x-chunks-retrieved" in response.headers
        assert response.headers["x-chunks-retrieved"].isdigit()


# ---------------------------------------------------------------------------
# POST /api/v1/ingest
# ---------------------------------------------------------------------------


class TestV1Ingest:
    def _mock_ingest(self, docs=None):
        from langchain_core.documents import Document

        if docs is None:
            docs = [Document(
                page_content="Content.",
                metadata={"source": "data/raw/manual.pdf", "page": 0},
            )]
        return (
            patch("app.api.v1.routes.load_directory", return_value=docs),
            patch("app.api.v1.routes.embed_texts", return_value=[[0.1] * 768]),
            patch("app.api.v1.routes.store.upsert_chunks"),
        )

    def test_returns_200(self):
        p_load, p_embed, p_upsert = self._mock_ingest()
        with p_load, p_embed, p_upsert:
            assert client.post("/api/v1/ingest", json={}).status_code == 200

    def test_response_schema(self):
        p_load, p_embed, p_upsert = self._mock_ingest()
        with p_load, p_embed, p_upsert:
            data = client.post("/api/v1/ingest", json={}).json()
        assert {"files_processed", "chunks_created", "chunks_upserted", "errors"}.issubset(
            data.keys()
        )

    def test_files_processed_count(self):
        p_load, p_embed, p_upsert = self._mock_ingest()
        with p_load, p_embed, p_upsert:
            data = client.post("/api/v1/ingest", json={}).json()
        assert data["files_processed"] == 1

    def test_no_pdfs_returns_error(self):
        with patch("app.api.v1.routes.load_directory", return_value=[]):
            data = client.post("/api/v1/ingest", json={}).json()
        assert data["files_processed"] == 0
        assert len(data["errors"]) == 1

    def test_chunks_created_positive(self):
        p_load, p_embed, p_upsert = self._mock_ingest()
        with p_load, p_embed, p_upsert:
            data = client.post("/api/v1/ingest", json={}).json()
        assert data["chunks_created"] > 0
