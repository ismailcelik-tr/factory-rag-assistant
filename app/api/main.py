"""FastAPI application entry point.

Run with:  uvicorn app.api.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("factory-rag-assistant starting up.")
    yield
    logger.info("factory-rag-assistant shutting down.")


app = FastAPI(title="factory-rag-assistant", version="0.1.0", lifespan=lifespan)
app.include_router(router)
