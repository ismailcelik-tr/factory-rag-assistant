"""Structured logging middleware for /api/v1/ask requests.

Logs four fields per request:
  query_hash       – SHA-256 of the query string, first 16 hex chars
  role             – role value from request body
  chunks_retrieved – value of X-Chunks-Retrieved response header (set by route handler)
  response_time_ms – wall-clock latency in milliseconds
"""

import hashlib
import json
import logging
import time

from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("factory_rag.access")


async def ask_logging_middleware(request: Request, call_next) -> Response:
    if request.url.path != "/api/v1/ask" or request.method != "POST":
        return await call_next(request)

    body = await request.body()
    start = time.monotonic()
    response = await call_next(request)
    elapsed_ms = round((time.monotonic() - start) * 1000)

    try:
        data = json.loads(body)
        query: str = data.get("query", "")
        role: str = data.get("role", "unknown")
    except Exception:
        query, role = "", "unknown"

    query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
    chunks_retrieved = response.headers.get("X-Chunks-Retrieved", "unknown")

    logger.info(
        "ask query_hash=%s role=%s chunks_retrieved=%s response_time_ms=%d",
        query_hash,
        role,
        chunks_retrieved,
        elapsed_ms,
    )
    return response
