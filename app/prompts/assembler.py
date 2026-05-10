"""Assemble system and user prompts from templates and retrieved chunks.

Prompt files live in prompts/ at the project root (not inside app/).
build_system_prompt raises FileNotFoundError if the role template is missing —
this is intentional so misconfigured roles fail loudly.
"""

from pathlib import Path

_PROMPTS_DIR = Path("prompts")


def _load_template(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def build_system_prompt(role: str) -> str:
    """Return the full system prompt for the given role.

    Concatenates prompts/system/base.md and prompts/roles/<role>.md.
    """
    base = _load_template(_PROMPTS_DIR / "system" / "base.md")
    role_template = _load_template(_PROMPTS_DIR / "roles" / f"{role}.md")
    return f"{base}\n\n{role_template}"


def build_user_message(query: str, chunks: list[dict]) -> str:
    """Return the user-turn message containing context blocks and the question.

    Each chunk is formatted as:
      [Source: <filename> | Page <n> | Section: <heading>]
      <chunk text>
    """
    context_blocks = [
        (
            f'[Source: {Path(chunk["source_file"]).name} | '
            f'Page {chunk["page_number"]} | '
            f'Section: {chunk["section_heading"]}]\n'
            f'{chunk["text"]}'
        )
        for chunk in chunks
    ]
    context = "\n\n".join(context_blocks)
    return f"Context:\n\n{context}\n\nQuestion: {query}"
