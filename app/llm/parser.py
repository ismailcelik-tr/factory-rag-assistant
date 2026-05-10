"""Extract structured citations from raw LLM response text.

The model is instructed (via base.md) to embed citations in the format:
  [cite: filename, p.N, "Section Name"]

This module parses those markers into Citation objects.
"""

import re

from app.api.schemas import Citation

_CITE_PATTERN = re.compile(
    r'\[cite:\s*([^,\]]+),\s*p\.(\d+),\s*"([^"]+)"\]'
)


def extract_citations(text: str) -> list[Citation]:
    """Parse all [cite: ...] markers in text and return Citation objects."""
    return [
        Citation(
            source_file=m.group(1).strip(),
            page_number=int(m.group(2)),
            section_heading=m.group(3).strip(),
        )
        for m in _CITE_PATTERN.finditer(text)
    ]
