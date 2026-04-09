"""Celery task definitions."""

from __future__ import annotations

import logging
from pathlib import Path

from app.workers import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.workers.tasks.ingest_federal_title")
def ingest_federal_title(self, title_number: int) -> dict:
    """Background task to ingest a single federal title."""
    from app.ingestion.pipeline import FederalIngestionPipeline

    logger.info(f"Task: ingesting Title {title_number}")
    pipeline = FederalIngestionPipeline()
    count = pipeline.ingest_title(title_number)
    return {"title_number": title_number, "chunks": count}


@celery_app.task(bind=True, name="app.workers.tasks.process_document_upload")
def process_document_upload(
    self,
    file_path: str,
    upload_id: str,
    file_name: str,
) -> dict:
    """Background task to process an uploaded document."""
    from app.document_ingestion import parse_and_chunk

    logger.info(f"Task: processing document {file_name} (upload_id={upload_id})")
    path = Path(file_path)

    chunks = parse_and_chunk(path, upload_id)
    return {
        "upload_id": upload_id,
        "file_name": file_name,
        "chunks": len(chunks),
    }


@celery_app.task(bind=True, name="app.workers.tasks.ingest_all_federal_titles")
def ingest_all_federal_titles(self) -> dict:
    """Background task to ingest all configured federal titles."""
    from app.core.config import settings
    from app.ingestion.pipeline import FederalIngestionPipeline

    logger.info("Task: ingesting all federal titles")
    pipeline = FederalIngestionPipeline()
    results = pipeline.ingest_all()
    return {str(k): v for k, v in results.items()}
