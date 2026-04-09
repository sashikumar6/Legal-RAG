"""Pydantic schemas for API request/response models and internal data structures."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class QueryMode(str, Enum):
    FEDERAL = "federal"
    DOCUMENT = "document"
    AUTO = "auto"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT = "insufficient"


class IngestionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000, description="User question")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    upload_id: Optional[str] = Field(None, description="Upload ID to scope document retrieval")
    mode: QueryMode = Field(QueryMode.AUTO, description="Query mode: federal, document, or auto-detect")


class Citation(BaseModel):
    source_type: str = Field(..., description="federal or document")
    document_id: str
    text: str = Field(..., description="Cited text snippet")
    # Federal-specific
    title_number: Optional[int] = None
    section_number: Optional[str] = None
    canonical_citation: Optional[str] = None
    # Document-specific
    page_number: Optional[int] = None
    heading: Optional[str] = None
    section_label: Optional[str] = None
    clause_title: Optional[str] = None
    # Retrieval metadata
    relevance_score: Optional[float] = None
    chunk_index: Optional[int] = None


class ChatResponse(BaseModel):
    answer: str
    mode: str = Field(..., description="Resolved mode: federal or document")
    confidence: ConfidenceLevel
    confidence_score: Optional[float] = Field(None, description="Quantitative retrieval confidence score")
    citations: list[Citation] = Field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    disclaimer: str = (
        "This information is for educational purposes only and does not constitute legal advice. "
        "Consult a qualified attorney for legal guidance."
    )
    session_id: str
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Document Upload
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    upload_id: str
    file_name: str
    file_type: str
    status: IngestionStatus
    chunk_count: Optional[int] = None
    message: str


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

class RetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1)
    mode: QueryMode = Field(QueryMode.FEDERAL)
    upload_id: Optional[str] = None
    top_k: int = Field(10, ge=1, le=50)
    title_filter: Optional[list[int]] = None


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResponse(BaseModel):
    chunks: list[RetrievedChunk]
    mode: str
    query: str
    total_results: int


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, bool]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Federal Chunk Metadata
# ---------------------------------------------------------------------------

class FederalChunkMetadata(BaseModel):
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    corpus: str = "uscode"
    jurisdiction: str = "federal"
    title_number: int
    title_name: str
    chapter: Optional[str] = None
    subchapter: Optional[str] = None
    part: Optional[str] = None
    subpart: Optional[str] = None
    section_number: Optional[str] = None
    subsection_path: Optional[str] = None
    heading: Optional[str] = None
    canonical_citation: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    release_point: Optional[str] = None
    publication_version: Optional[str] = None
    chunk_index: int = 0
    parent_chunk_id: Optional[str] = None
    text: str = ""
    normalized_text: str = ""
    text_hash: str = ""


# ---------------------------------------------------------------------------
# Document Chunk Metadata
# ---------------------------------------------------------------------------

class DocumentChunkMetadata(BaseModel):
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    upload_id: str
    file_name: str
    file_type: str
    page_number: Optional[int] = None
    heading: Optional[str] = None
    section_label: Optional[str] = None
    clause_title: Optional[str] = None
    chunk_index: int = 0
    parent_chunk_id: Optional[str] = None
    text: str = ""
    normalized_text: str = ""
    text_hash: str = ""


# ---------------------------------------------------------------------------
# Agent State
# ---------------------------------------------------------------------------

class AgentState(BaseModel):
    """State object passed through the LangGraph workflow."""
    query: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    upload_id: Optional[str] = None

    # Classification
    resolved_mode: Optional[str] = None
    needs_clarification: bool = False
    clarification_question: Optional[str] = None

    # Entities & hints
    entities: list[str] = Field(default_factory=list)
    title_hints: list[int] = Field(default_factory=list)
    document_scope: Optional[str] = None

    # Plan
    retrieval_plan: Optional[dict[str, Any]] = None

    # Retrieval
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_score: float = 0.0
    retrieval_sufficient: bool = False

    # Generation
    draft_answer: Optional[str] = None
    citations: list[dict[str, Any]] = Field(default_factory=list)

    # Verification
    verification_passed: bool = False
    verification_issues: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.INSUFFICIENT

    # Retry tracking
    retrieval_retry_count: int = 0
    generation_retry_count: int = 0

    # Final output
    final_answer: Optional[str] = None
    error: Optional[str] = None
