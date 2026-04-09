"""FastAPI route definitions — wired to real Qdrant + OpenAI clients."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from app.core.config import settings
from app.core.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    ReadinessResponse,
    RetrievalRequest,
    RetrievalResponse,
    UploadResponse,
)
from app.observability import documents_uploaded_total

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router instances
# ---------------------------------------------------------------------------

router = APIRouter()
health_router = APIRouter(tags=["health"])

# ---------------------------------------------------------------------------
# Real client initialization
# ---------------------------------------------------------------------------

_qdrant_client = None
_embedding_fn = None


def _get_clients():
    """Lazy-initialize Qdrant client and embedding function."""
    global _qdrant_client, _embedding_fn

    if _qdrant_client is None:
        try:
            from app.core.qdrant_client import create_qdrant_client, ensure_collections
            _qdrant_client = create_qdrant_client()
            if _qdrant_client:
                ensure_collections(_qdrant_client)
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")

    if _embedding_fn is None:
        try:
            from app.core.llm import create_embedding_fn, check_openai_configured
            if check_openai_configured():
                _embedding_fn = create_embedding_fn()
                logger.info("OpenAI embedding function initialized")
            else:
                logger.warning(
                    "OPENAI_API_KEY not set — embedding/LLM features disabled. "
                    "Set it in .env or environment to enable real AI features."
                )
        except Exception as e:
            logger.error(f"Failed to initialize embedding function: {e}")

    return _qdrant_client, _embedding_fn


def _get_chat_service():
    from app.services import ChatService
    client, embed_fn = _get_clients()
    return ChatService(qdrant_client=client, embedding_fn=embed_fn)


def _get_upload_service():
    from app.services import UploadService
    client, embed_fn = _get_clients()
    return UploadService(qdrant_client=client, embedding_fn=embed_fn)


def _get_retrieval_service():
    from app.services import RetrievalService
    client, embed_fn = _get_clients()
    return RetrievalService(qdrant_client=client, embedding_fn=embed_fn)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(request: ChatRequest):
    """
    Submit a query for AI-powered legal research.
    
    Mode is auto-detected or can be explicitly set:
    - federal: Search the U.S. Code corpus
    - document: Search an uploaded document (requires upload_id)
    - auto: System detects the appropriate mode
    """
    try:
        service = _get_chat_service()
        response = await service.process_query(request)
        return response
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=UploadResponse, tags=["upload"])
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a PDF or DOCX document for document-specific Q&A.
    
    The document will be parsed, chunked, embedded, and indexed for retrieval.
    Returns an upload_id to use in subsequent chat requests.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    suffix = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if suffix not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Allowed: {settings.allowed_extensions}",
        )

    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB",
        )

    file_type = suffix.lstrip(".")
    documents_uploaded_total.labels(file_type=file_type).inc()

    try:
        service = _get_upload_service()
        response = await service.process_upload(
            file_name=file.filename,
            file_content=content,
            file_type=file_type,
        )
        return response
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload processing error: {str(e)}")


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

@router.post("/retrieval", response_model=RetrievalResponse, tags=["retrieval"])
async def retrieve(request: RetrievalRequest):
    """
    Direct retrieval endpoint for testing and debugging.
    Returns raw retrieval results without answer generation.
    """
    try:
        service = _get_retrieval_service()
        response = await service.retrieve(request)
        return response
    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        raise HTTPException(status_code=500, detail=f"Retrieval error: {str(e)}")


# ---------------------------------------------------------------------------
# Health Checks
# ---------------------------------------------------------------------------

@health_router.get("/health", response_model=HealthResponse, tags=["health"])
async def health():
    """Overall health check."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.environment.value,
    )


@health_router.get("/health/live", tags=["health"])
async def liveness():
    """Liveness probe."""
    return {"status": "alive"}


@health_router.get("/health/ready", response_model=ReadinessResponse, tags=["health"])
async def readiness():
    """Readiness probe checking dependent services."""
    checks = {
        "database": True,
        "redis": True,
        "qdrant": _qdrant_client is not None,
        "openai": bool(settings.openai_api_key),
    }

    try:
        from app.database import async_engine
        async with async_engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception:
        checks["database"] = False

    try:
        import redis
        r = redis.from_url(settings.redis_url)
        r.ping()
    except Exception:
        checks["redis"] = False

    all_ready = all(checks.values())
    return ReadinessResponse(
        status="ready" if all_ready else "not_ready",
        checks=checks,
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@health_router.get("/metrics", tags=["observability"])
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
