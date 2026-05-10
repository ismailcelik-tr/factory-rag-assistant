"""Pydantic request/response models for the FastAPI application.

Role enum values must exactly match the prompt template filenames
in prompts/roles/ (e.g. "tech_service" → prompts/roles/tech_service.md).
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Role(str, Enum):
    rd_engineer = "rd_engineer"
    tech_service = "tech_service"
    sales = "sales"
    purchasing = "purchasing"
    production = "production"
    customer_support = "customer_support"


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    role: Role
    product_family: Optional[str] = None


class Citation(BaseModel):
    source_file: str
    page_number: int
    section_heading: str


class AskResponse(BaseModel):
    answer: Optional[str]
    citations: list[Citation]
    role: str
    model: str
    chunks_used: int
    no_results: bool = False


class IngestRequest(BaseModel):
    path: str = "data/raw/"
    document_type: Optional[str] = None
    product_family: Optional[str] = None


class IngestResponse(BaseModel):
    files_processed: int
    chunks_created: int
    chunks_upserted: int
    errors: list[str]
