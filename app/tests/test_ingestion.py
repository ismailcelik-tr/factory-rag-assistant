"""Tests for Step 2: ingestion pipeline (chunker + metadata).

loader.py is not tested here because it wraps PyPDFLoader and requires a
real PDF file on disk. Manual verification steps are in the Step 2 section
of docs/IMPLEMENTATION_PLAN.md.

These tests exercise chunker.split_documents() and metadata.enrich() using
synthetic LangChain Documents so they run offline with no dependencies on
Ollama, ChromaDB, or any PDF files.
"""

from langchain_core.documents import Document

from app.ingestion.chunker import split_documents
from app.ingestion.metadata import _detect_heading, _infer_document_type, enrich

# ---------------------------------------------------------------------------
# chunker
# ---------------------------------------------------------------------------


class TestSplitDocuments:
    def _make_doc(self, text: str, source: str = "test.pdf", page: int = 0) -> Document:
        return Document(page_content=text, metadata={"source": source, "page": page})

    def test_short_doc_produces_one_chunk(self):
        doc = self._make_doc("Short content.")
        chunks = split_documents([doc])
        assert len(chunks) == 1

    def test_long_doc_is_split(self):
        # 4500 chars → at least 3 chunks at 1500-char target
        long_text = "word " * 900
        doc = self._make_doc(long_text)
        chunks = split_documents([doc])
        assert len(chunks) >= 3

    def test_metadata_preserved_on_chunks(self):
        doc = self._make_doc("Some content.", source="data/raw/manual.pdf", page=3)
        chunks = split_documents([doc])
        for chunk in chunks:
            assert chunk.metadata["source"] == "data/raw/manual.pdf"
            assert chunk.metadata["page"] == 3

    def test_overlap_means_adjacent_chunks_share_content(self):
        # Generate text long enough to produce at least two chunks
        text = "The quick brown fox jumps over the lazy dog. " * 80
        doc = self._make_doc(text)
        chunks = split_documents([doc])
        assert len(chunks) >= 2
        # Last 200 chars of chunk[0] should appear somewhere in chunk[1]
        tail = chunks[0].page_content[-100:]
        assert tail in chunks[1].page_content

    def test_empty_document_list(self):
        assert split_documents([]) == []

    def test_chunk_size_within_bound(self):
        long_text = "word " * 1000
        doc = self._make_doc(long_text)
        chunks = split_documents([doc])
        # No chunk should exceed chunk_size + overlap (1500 + 200)
        for chunk in chunks:
            assert len(chunk.page_content) <= 1700


# ---------------------------------------------------------------------------
# metadata — document type inference
# ---------------------------------------------------------------------------


class TestInferDocumentType:
    def test_manual(self):
        assert _infer_document_type("X200_user_manual.pdf") == "manual"

    def test_user_guide(self):
        assert _infer_document_type("product_user_guide_v2.pdf") == "manual"

    def test_datasheet(self):
        assert _infer_document_type("X200_datasheet_rev3.pdf") == "datasheet"

    def test_service(self):
        assert _infer_document_type("service_documentation.pdf") == "service"

    def test_installation(self):
        assert _infer_document_type("installation_instructions.pdf") == "installation"

    def test_troubleshooting(self):
        assert _infer_document_type("troubleshooting_guide.pdf") == "troubleshooting"

    def test_spec(self):
        assert _infer_document_type("technical_specification.pdf") == "spec"

    def test_unknown_falls_back(self):
        assert _infer_document_type("document_2024.pdf") == "unknown"


# ---------------------------------------------------------------------------
# metadata — heading detection
# ---------------------------------------------------------------------------


class TestDetectHeading:
    def test_numbered_section(self):
        text = "3.2 Motor Calibration\nThe motor must be calibrated before use."
        assert _detect_heading(text) == "3.2 Motor Calibration"

    def test_nested_numbered_section(self):
        text = "1.2.3 Safety Precautions\nAlways wear protective equipment."
        assert _detect_heading(text) == "1.2.3 Safety Precautions"

    def test_section_keyword(self):
        text = "Section 4 Installation\nFollow these steps carefully."
        assert _detect_heading(text) == "Section 4 Installation"

    def test_chapter_keyword(self):
        text = "Chapter 2 Overview\nThis chapter provides."
        assert _detect_heading(text) == "Chapter 2 Overview"

    def test_all_caps_short_line(self):
        text = "SAFETY WARNINGS\nDo not operate without reading."
        assert _detect_heading(text) == "SAFETY WARNINGS"

    def test_all_caps_long_line_ignored(self):
        # Lines ≥ 60 chars should not be treated as headings
        long_caps = "A" * 60
        text = f"{long_caps}\nSome content."
        result = _detect_heading(text)
        assert result != long_caps

    def test_no_heading_returns_none(self):
        text = "The pressure relief valve opens at 3.5 bar. Close the valve after use."
        assert _detect_heading(text) is None

    def test_heading_search_stops_at_sentence_end(self):
        # The all-caps line comes after a sentence — should not be found
        text = "First sentence ends here.\nSAFETY WARNINGS\nMore text."
        assert _detect_heading(text) is None


# ---------------------------------------------------------------------------
# metadata — enrich
# ---------------------------------------------------------------------------


class TestEnrich:
    def _make_chunk(
        self, text: str, source: str = "data/raw/manual.pdf", page: int = 0
    ) -> Document:
        return Document(page_content=text, metadata={"source": source, "page": page})

    def test_basic_fields_present(self):
        chunks = [self._make_chunk("Some content about the motor.")]
        result = enrich(chunks)
        assert len(result) == 1
        rec = result[0]
        required = {
            "chunk_id", "text", "source_file", "page_number",
            "section_heading", "document_type", "product_family", "token_count",
        }
        assert required.issubset(rec.keys())

    def test_page_number_is_one_indexed(self):
        chunk = self._make_chunk("text", page=0)
        result = enrich([chunk])
        assert result[0]["page_number"] == 1

    def test_page_number_offset(self):
        chunk = self._make_chunk("text", page=5)
        result = enrich([chunk])
        assert result[0]["page_number"] == 6

    def test_product_family_explicit(self):
        chunk = self._make_chunk("text")
        result = enrich([chunk], product_family="X200")
        assert result[0]["product_family"] == "x200"

    def test_product_family_defaults_to_unknown(self):
        chunk = self._make_chunk("text")
        result = enrich([chunk])
        assert result[0]["product_family"] == "unknown"

    def test_document_type_explicit(self):
        chunk = self._make_chunk("text")
        result = enrich([chunk], document_type="service")
        assert result[0]["document_type"] == "service"

    def test_document_type_inferred_from_filename(self):
        chunk = self._make_chunk("text", source="data/raw/X200_datasheet.pdf")
        result = enrich([chunk])
        assert result[0]["document_type"] == "datasheet"

    def test_chunk_id_format(self):
        chunk = self._make_chunk("text", source="data/raw/manual.pdf", page=11)
        result = enrich([chunk], document_type="manual", product_family="X200")
        # format: <doc_type>_<family>_p<page>_<seq>
        assert result[0]["chunk_id"] == "manual_x200_p012_000"

    def test_chunk_id_sequence_increments(self):
        chunks = [
            self._make_chunk("chunk one"),
            self._make_chunk("chunk two"),
            self._make_chunk("chunk three"),
        ]
        result = enrich(chunks)
        ids = [r["chunk_id"] for r in result]
        # All from same source, so seq should increment
        assert ids[0].endswith("_000")
        assert ids[1].endswith("_001")
        assert ids[2].endswith("_002")

    def test_sequence_resets_for_new_source(self):
        chunks = [
            self._make_chunk("first doc chunk", source="data/raw/doc_a.pdf"),
            self._make_chunk("second doc chunk", source="data/raw/doc_b.pdf"),
        ]
        result = enrich(chunks)
        assert result[0]["chunk_id"].endswith("_000")
        assert result[1]["chunk_id"].endswith("_000")

    def test_heading_detected(self):
        chunk = self._make_chunk("3.2 Motor Calibration\nCalibrate to 1500 RPM.")
        result = enrich([chunk])
        assert result[0]["section_heading"] == "3.2 Motor Calibration"

    def test_heading_carries_forward(self):
        chunks = [
            self._make_chunk("SAFETY WARNINGS\nFirst paragraph."),
            self._make_chunk("Continued content without a new heading."),
        ]
        result = enrich(chunks)
        assert result[0]["section_heading"] == "SAFETY WARNINGS"
        assert result[1]["section_heading"] == "SAFETY WARNINGS"

    def test_heading_resets_for_new_source(self):
        chunks = [
            self._make_chunk("SAFETY WARNINGS\nContent.", source="data/raw/doc_a.pdf"),
            self._make_chunk("Paragraph with no heading.", source="data/raw/doc_b.pdf"),
        ]
        result = enrich(chunks)
        assert result[0]["section_heading"] == "SAFETY WARNINGS"
        assert result[1]["section_heading"] == "[No Heading]"

    def test_no_heading_fallback(self):
        chunk = self._make_chunk("This is a paragraph. No heading here.")
        result = enrich([chunk])
        assert result[0]["section_heading"] == "[No Heading]"

    def test_section_heading_never_empty(self):
        chunks = [self._make_chunk(f"Content block {i}.") for i in range(5)]
        result = enrich(chunks)
        for rec in result:
            assert rec["section_heading"]  # truthy and non-empty

    def test_token_count_is_word_count(self):
        chunk = self._make_chunk("one two three four five")
        result = enrich([chunk])
        assert result[0]["token_count"] == 5

    def test_token_count_is_positive(self):
        chunks = [self._make_chunk("some content")]
        result = enrich(chunks)
        assert result[0]["token_count"] > 0

    def test_source_file_preserved(self):
        chunk = self._make_chunk("text", source="data/raw/subfolder/doc.pdf")
        result = enrich([chunk])
        assert result[0]["source_file"] == "data/raw/subfolder/doc.pdf"

    def test_empty_input(self):
        result = enrich([])
        assert result == []
