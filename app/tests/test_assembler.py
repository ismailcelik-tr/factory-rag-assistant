"""Tests for Step 7: prompt assembler.

All tests are pure unit tests — no Ollama or ChromaDB required.
Template loading uses the real prompts/ directory (already on disk).
"""

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_CHUNK = {
    "text": "The motor must be calibrated before first use.",
    "score": 0.92,
    "source_file": "data/raw/X200_manual.pdf",
    "page_number": 3,
    "section_heading": "3.2 Motor Calibration",
    "document_type": "manual",
    "product_family": "x200",
}


# ---------------------------------------------------------------------------
# build_system_prompt
# ---------------------------------------------------------------------------


class TestBuildSystemPrompt:
    def test_returns_string(self):
        from app.prompts.assembler import build_system_prompt

        result = build_system_prompt("tech_service")
        assert isinstance(result, str)

    def test_contains_base_content(self):
        from pathlib import Path

        from app.prompts.assembler import build_system_prompt

        base_text = Path("prompts/system/base.md").read_text(encoding="utf-8").strip()
        result = build_system_prompt("tech_service")
        assert base_text in result

    def test_contains_role_content(self):
        from pathlib import Path

        from app.prompts.assembler import build_system_prompt

        role_text = Path("prompts/roles/tech_service.md").read_text(encoding="utf-8").strip()
        result = build_system_prompt("tech_service")
        assert role_text in result

    def test_base_comes_before_role(self):
        from pathlib import Path

        from app.prompts.assembler import build_system_prompt

        base_text = Path("prompts/system/base.md").read_text(encoding="utf-8").strip()
        role_text = Path("prompts/roles/tech_service.md").read_text(encoding="utf-8").strip()
        result = build_system_prompt("tech_service")
        assert result.index(base_text) < result.index(role_text)

    def test_all_six_roles_load(self):
        from app.prompts.assembler import build_system_prompt

        roles = ["rd_engineer", "tech_service", "sales", "purchasing", "production",
                 "customer_support"]
        for role in roles:
            result = build_system_prompt(role)
            assert len(result) > 0

    def test_unknown_role_raises_file_not_found(self):
        from app.prompts.assembler import build_system_prompt

        with pytest.raises(FileNotFoundError):
            build_system_prompt("nonexistent_role")

    def test_result_is_nonempty(self):
        from app.prompts.assembler import build_system_prompt

        result = build_system_prompt("rd_engineer")
        assert len(result.strip()) > 0


# ---------------------------------------------------------------------------
# build_user_message
# ---------------------------------------------------------------------------


class TestBuildUserMessage:
    def test_returns_string(self):
        from app.prompts.assembler import build_user_message

        result = build_user_message("What is this?", [_SAMPLE_CHUNK])
        assert isinstance(result, str)

    def test_contains_query(self):
        from app.prompts.assembler import build_user_message

        result = build_user_message("What is the max temperature?", [_SAMPLE_CHUNK])
        assert "What is the max temperature?" in result

    def test_contains_chunk_text(self):
        from app.prompts.assembler import build_user_message

        result = build_user_message("test?", [_SAMPLE_CHUNK])
        assert _SAMPLE_CHUNK["text"] in result

    def test_source_label_uses_basename(self):
        from app.prompts.assembler import build_user_message

        result = build_user_message("test?", [_SAMPLE_CHUNK])
        assert "X200_manual.pdf" in result
        assert "data/raw/" not in result

    def test_source_label_contains_page(self):
        from app.prompts.assembler import build_user_message

        result = build_user_message("test?", [_SAMPLE_CHUNK])
        assert "Page 3" in result

    def test_source_label_contains_section(self):
        from app.prompts.assembler import build_user_message

        result = build_user_message("test?", [_SAMPLE_CHUNK])
        assert "3.2 Motor Calibration" in result

    def test_multiple_chunks_all_included(self):
        from app.prompts.assembler import build_user_message

        chunks = [
            dict(_SAMPLE_CHUNK, text="First chunk content.", page_number=1),
            dict(_SAMPLE_CHUNK, text="Second chunk content.", page_number=2),
            dict(_SAMPLE_CHUNK, text="Third chunk content.", page_number=3),
        ]
        result = build_user_message("test?", chunks)
        assert "First chunk content." in result
        assert "Second chunk content." in result
        assert "Third chunk content." in result

    def test_question_comes_after_context(self):
        from app.prompts.assembler import build_user_message

        query = "What is the calibration speed?"
        result = build_user_message(query, [_SAMPLE_CHUNK])
        context_pos = result.index("Context:")
        question_pos = result.index(f"Question: {query}")
        assert context_pos < question_pos

    def test_empty_chunks_still_includes_question(self):
        from app.prompts.assembler import build_user_message

        result = build_user_message("Any question?", [])
        assert "Any question?" in result

    def test_source_label_format(self):
        from app.prompts.assembler import build_user_message

        result = build_user_message("test?", [_SAMPLE_CHUNK])
        assert "[Source: X200_manual.pdf | Page 3 | Section: 3.2 Motor Calibration]" in result
