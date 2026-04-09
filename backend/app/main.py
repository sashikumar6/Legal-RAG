"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.observability.middleware import MetricsMiddleware

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment.value}")
    logger.info(f"Federal XML base path: {settings.federal_xml_base_path}")
    logger.info(f"Qdrant: {settings.qdrant_host}:{settings.qdrant_port} (local_mode={settings.dev_qdrant_local_mode})")
    logger.info(f"OpenAI API key configured: {bool(settings.openai_api_key)}")
    logger.info(f"LLM model: {settings.llm_model}, Embedding model: {settings.embedding_model}")

    if not settings.openai_api_key:
        logger.warning(
            "⚠ OPENAI_API_KEY is NOT set. LLM generation and embeddings will fail. "
            "Set it in your .env file or environment."
        )

    yield

    # Shutdown
    logger.info("Shutting down application")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Dual-Mode Federal Law and Document AI Intake Agent. "
            "Provides AI-powered legal research with strictly isolated retrieval modes "
            "for federal U.S. Code and uploaded legal documents."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Metrics middleware
    app.add_middleware(MetricsMiddleware)

    # Include routers
    from app.api.routes import router, health_router
    app.include_router(router, prefix=settings.api_prefix)
    app.include_router(health_router)

    return app


app = create_app()
