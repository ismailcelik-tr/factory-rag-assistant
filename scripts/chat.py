"""Interactive CLI for querying the RAG pipeline.

Usage:
    python scripts/chat.py --role tech_service
    python scripts/chat.py --role rd_engineer --family X200
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # noqa: E402

from app.api.schemas import Role  # noqa: E402
from app.config import settings  # noqa: E402
from app.llm.ollama_provider import OllamaProvider  # noqa: E402
from app.llm.parser import extract_citations  # noqa: E402
from app.prompts.assembler import build_system_prompt, build_user_message  # noqa: E402
from app.retrieval.retriever import retrieve  # noqa: E402

logging.basicConfig(level=logging.WARNING)


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive RAG query CLI.")
    parser.add_argument(
        "--role",
        required=True,
        choices=[r.value for r in Role],
        help="User role (determines prompt template)",
    )
    parser.add_argument("--family", default=None, help="Filter results by product family")
    parser.add_argument("--top-k", type=int, default=settings.top_k,
                        help=f"Number of chunks to retrieve (default: {settings.top_k})")
    args = parser.parse_args()

    print(f"\nfactory-rag-assistant  |  role={args.role}  |  family={args.family or 'all'}")
    print("Type your question and press Enter. Leave blank or type 'quit' to exit.\n")

    provider = OllamaProvider()

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not query or query.lower() == "quit":
            break

        chunks = retrieve(query, top_k=args.top_k, product_family=args.family)
        if not chunks:
            print("Assistant: No relevant documents found.\n")
            continue

        system_prompt = build_system_prompt(args.role)
        user_message = build_user_message(query, chunks)
        answer = provider.generate(system_prompt, user_message)

        print(f"\nAssistant: {answer}")

        citations = extract_citations(answer)
        if citations:
            print("\nSources:")
            for c in citations:
                print(f"  • {c.source_file}, p.{c.page_number} — {c.section_heading}")
        else:
            print("\nSources (context chunks used):")
            for c in chunks:
                name = Path(c["source_file"]).name
                print(f"  • {name}, p.{c['page_number']} — {c['section_heading']}")
        print()


if __name__ == "__main__":
    main()
