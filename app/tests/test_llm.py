"""Tests for Step 6: LLM provider and citation parser.

OllamaProvider integration tests require Ollama running with gemma4:e4b pulled.
Parser tests are pure unit tests — no external dependencies.
"""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# parser — pure unit tests
# ---------------------------------------------------------------------------


class TestExtractCitations:
    def test_single_citation(self):
        from app.llm.parser import extract_citations

        text = (
            'The max temperature is 85°C '
            '[cite: X200_datasheet.pdf, p.4, "4.1 Thermal Specifications"].'
        )
        citations = extract_citations(text)
        assert len(citations) == 1
        c = citations[0]
        assert c.source_file == "X200_datasheet.pdf"
        assert c.page_number == 4
        assert c.section_heading == "4.1 Thermal Specifications"

    def test_multiple_citations(self):
        from app.llm.parser import extract_citations

        text = (
            'Step one [cite: manual.pdf, p.2, "Installation"]. '
            'Step two [cite: service.pdf, p.8, "3.1 Wiring"].'
        )
        citations = extract_citations(text)
        assert len(citations) == 2
        assert citations[0].source_file == "manual.pdf"
        assert citations[1].source_file == "service.pdf"

    def test_no_citations_returns_empty(self):
        from app.llm.parser import extract_citations

        assert extract_citations("Plain answer with no citations.") == []

    def test_page_number_is_int(self):
        from app.llm.parser import extract_citations

        citations = extract_citations('[cite: doc.pdf, p.12, "Section"]')
        assert isinstance(citations[0].page_number, int)
        assert citations[0].page_number == 12

    def test_whitespace_trimmed_from_source_file(self):
        from app.llm.parser import extract_citations

        citations = extract_citations('[cite:  doc.pdf , p.1, "Section"]')
        assert citations[0].source_file == "doc.pdf"

    def test_whitespace_trimmed_from_heading(self):
        from app.llm.parser import extract_citations

        citations = extract_citations('[cite: doc.pdf, p.1, "  My Section  "]')
        assert citations[0].section_heading == "My Section"

    def test_citation_mid_sentence(self):
        from app.llm.parser import extract_citations

        text = 'Use the valve [cite: manual.pdf, p.3, "Safety"] carefully.'
        assert len(extract_citations(text)) == 1

    def test_malformed_cite_not_matched(self):
        from app.llm.parser import extract_citations

        # Missing quotes around section heading
        assert extract_citations("[cite: doc.pdf, p.1, No Quotes]") == []

    def test_returns_citation_objects(self):
        from app.api.schemas import Citation
        from app.llm.parser import extract_citations

        result = extract_citations('[cite: doc.pdf, p.1, "Section"]')
        assert isinstance(result[0], Citation)


# ---------------------------------------------------------------------------
# OllamaProvider — unit tests (mock httpx)
# ---------------------------------------------------------------------------


class TestOllamaProviderUnit:
    def _make_response(self, content: str):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": content}}
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_returns_response_content(self):
        with patch("app.llm.ollama_provider.httpx.post") as mock_post:
            mock_post.return_value = self._make_response("Hello from the model.")
            from app.llm.ollama_provider import OllamaProvider

            result = OllamaProvider().generate("System prompt.", "User message.")
        assert result == "Hello from the model."

    def test_payload_contains_both_messages(self):
        with patch("app.llm.ollama_provider.httpx.post") as mock_post:
            mock_post.return_value = self._make_response("ok")
            from app.llm.ollama_provider import OllamaProvider

            OllamaProvider().generate("sys", "usr")

        payload = mock_post.call_args[1]["json"]
        roles = [m["role"] for m in payload["messages"]]
        assert roles == ["system", "user"]

    def test_payload_stream_is_false(self):
        with patch("app.llm.ollama_provider.httpx.post") as mock_post:
            mock_post.return_value = self._make_response("ok")
            from app.llm.ollama_provider import OllamaProvider

            OllamaProvider().generate("sys", "usr")

        payload = mock_post.call_args[1]["json"]
        assert payload["stream"] is False

    def test_payload_uses_settings_model(self):
        from app.config import settings

        with patch("app.llm.ollama_provider.httpx.post") as mock_post:
            mock_post.return_value = self._make_response("ok")
            from app.llm.ollama_provider import OllamaProvider

            OllamaProvider().generate("sys", "usr")

        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == settings.llm_model

    def test_raises_on_http_error(self):
        import httpx

        with patch("app.llm.ollama_provider.httpx.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock()
            )
            mock_post.return_value = mock_resp
            from app.llm.ollama_provider import OllamaProvider

            with pytest.raises(httpx.HTTPStatusError):
                OllamaProvider().generate("sys", "usr")

    def test_timeout_is_120_seconds(self):
        with patch("app.llm.ollama_provider.httpx.post") as mock_post:
            mock_post.return_value = self._make_response("ok")
            from app.llm.ollama_provider import OllamaProvider

            OllamaProvider().generate("sys", "usr")

        assert mock_post.call_args[1]["timeout"] == 120.0


# ---------------------------------------------------------------------------
# Integration tests — require Ollama running with gemma4:e4b pulled
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
class TestOllamaProviderIntegration:
    def test_returns_nonempty_string(self):
        from app.llm.ollama_provider import OllamaProvider

        result = OllamaProvider().generate("You are helpful.", "Say hello in one word.")
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_implements_llm_provider(self):
        from app.llm.base import LLMProvider
        from app.llm.ollama_provider import OllamaProvider

        assert isinstance(OllamaProvider(), LLMProvider)
