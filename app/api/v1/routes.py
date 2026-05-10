"""Versioned API routes — /api/v1/

Identical business logic to app/api/routes.py with these additions:
- GET /roles endpoint for dynamic role discovery
- X-Chunks-Retrieved response header on /ask (read by logging middleware)
"""

import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, Response

from app.api.schemas import AskRequest, AskResponse, Citation, IngestRequest, IngestResponse, Role
from app.config import settings
from app.embeddings import store
from app.embeddings.embedder import embed_texts
from app.ingestion.chunker import split_documents
from app.ingestion.loader import load_directory
from app.ingestion.metadata import enrich, save_chunks
from app.llm.ollama_provider import OllamaProvider
from app.llm.parser import extract_citations
from app.prompts.assembler import build_system_prompt, build_user_message
from app.retrieval.retriever import retrieve

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


@router.get("/roles")
def roles() -> dict[str, list[str]]:
    return {"roles": [r.value for r in Role]}


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, response: Response) -> AskResponse:
    chunks = retrieve(
        query=request.query,
        top_k=settings.top_k,
        product_family=request.product_family,
    )

    response.headers["X-Chunks-Retrieved"] = str(len(chunks))

    if not chunks:
        return AskResponse(
            answer=None,
            citations=[],
            role=request.role.value,
            model=settings.llm_model,
            chunks_used=0,
            no_results=True,
        )

    system_prompt = build_system_prompt(request.role.value)
    user_message = build_user_message(request.query, chunks)
    raw_response = OllamaProvider().generate(system_prompt, user_message)

    citations = extract_citations(raw_response)

    if not citations:
        logger.warning("Model returned no citations — falling back to context chunks.")
        citations = [
            Citation(
                source_file=Path(c["source_file"]).name,
                page_number=c["page_number"],
                section_heading=c["section_heading"],
            )
            for c in chunks
        ]

    return AskResponse(
        answer=raw_response,
        citations=citations,
        role=request.role.value,
        model=settings.llm_model,
        chunks_used=len(chunks),
    )


@router.post("/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest = IngestRequest()) -> IngestResponse:
    errors: list[str] = []
    total_chunks_created = 0
    total_chunks_upserted = 0
    files_processed = 0

    docs = load_directory(request.path)
    if not docs:
        return IngestResponse(
            files_processed=0,
            chunks_created=0,
            chunks_upserted=0,
            errors=[f"No PDF files found under {request.path}"],
        )

    sources: dict[str, list] = {}
    for doc in docs:
        src = doc.metadata.get("source", "unknown")
        sources.setdefault(src, []).append(doc)

    for source, pages in sources.items():
        try:
            chunks_docs = split_documents(pages)
            chunks = enrich(
                chunks_docs,
                document_type=request.document_type,
                product_family=request.product_family,
            )
            save_chunks(chunks, settings.processed_path)
            embeddings = embed_texts([c["text"] for c in chunks])
            store.upsert_chunks(chunks, embeddings)
            total_chunks_created += len(chunks)
            total_chunks_upserted += len(chunks)
            files_processed += 1
        except Exception as exc:
            logger.error("Failed to process %s: %s", source, exc)
            errors.append(f"{Path(source).name}: {exc}")

    return IngestResponse(
        files_processed=files_processed,
        chunks_created=total_chunks_created,
        chunks_upserted=total_chunks_upserted,
        errors=errors,
    )


@router.get("/health")
def health() -> dict:
    ollama_status = "unreachable"
    try:
        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3.0)
        if r.status_code == 200:
            ollama_status = "reachable"
    except Exception:
        pass

    vector_store_status = "error"
    chunks_indexed = 0
    try:
        chunks_indexed = store.collection.count()
        vector_store_status = "ok"
    except Exception:
        pass

    overall = "ok" if ollama_status == "reachable" and vector_store_status == "ok" else "degraded"

    return {
        "status": overall,
        "ollama": ollama_status,
        "vector_store": vector_store_status,
        "chunks_indexed": chunks_indexed,
    }
