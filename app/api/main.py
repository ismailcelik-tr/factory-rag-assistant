"""FastAPI application entry point.

Run with:  uvicorn app.api.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.middleware import ask_logging_middleware
from app.api.routes import router
from app.api.v1.routes import router as v1_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("factory-rag-assistant starting up.")
    yield
    logger.info("factory-rag-assistant shutting down.")


app = FastAPI(title="factory-rag-assistant", version="0.1.0", lifespan=lifespan)

app.include_router(router)
app.include_router(v1_router)
app.add_middleware(BaseHTTPMiddleware, dispatch=ask_logging_middleware)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"error": str(exc.errors()[0]["msg"]), "code": "validation_error"},
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "code": f"http_{exc.status_code}"},
    )
