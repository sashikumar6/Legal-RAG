"""Isolated retrieval layer — strictly separates federal and document retrieval."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from app.core.config import settings
from app.core.schemas import QueryMode, RetrievedChunk
from app.observability import retrieval_by_mode_total, retrieval_latency_seconds, retrieval_requests_total

logger = logging.getLogger(__name__)


class FederalRetriever:
    """Retrieves evidence ONLY from the federal U.S. Code corpus in Qdrant.
    
    Never accesses uploaded documents. Never falls back to model-only answers.
    """

    def __init__(self, qdrant_client=None, embedding_fn=None):
        self.qdrant_client = qdrant_client
        self.embedding_fn = embedding_fn
        self.collection = settings.qdrant_federal_collection

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        title_filter: Optional[list[int]] = None,
        score_threshold: float = 0.0,
    ) -> list[RetrievedChunk]:
        """Search the federal corpus. Optionally filter by title numbers."""
        start = time.perf_counter()
        retrieval_requests_total.labels(mode="federal").inc()
        retrieval_by_mode_total.labels(mode="federal").inc()

        if self.qdrant_client is None or self.embedding_fn is None:
            logger.warning("Federal retriever not configured — returning empty results")
            return []

        try:
            query_embedding = self.embedding_fn([query])[0]
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return []

        # Build Qdrant filter
        search_filter = None
        if title_filter:
            from qdrant_client.models import FieldCondition, Filter, MatchAny
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="title_number",
                        match=MatchAny(any=title_filter),
                    )
                ]
            )

        try:
            results = self.qdrant_client.search(
                collection_name=self.collection,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=top_k,
                score_threshold=score_threshold,
            )
        except Exception as e:
            logger.error(f"Qdrant search error: {e}")
            return []

        chunks = []
        for hit in results:
            payload = hit.payload or {}
            chunks.append(RetrievedChunk(
                chunk_id=str(hit.id),
                text=payload.get("text", ""),
                score=hit.score,
                metadata={
                    "source_type": "federal",
                    "title_number": payload.get("title_number"),
                    "title_name": payload.get("title_name"),
                    "section_number": payload.get("section_number"),
                    "canonical_citation": payload.get("canonical_citation"),
                    "heading": payload.get("heading"),
                    "chapter": payload.get("chapter"),
                    "subchapter": payload.get("subchapter"),
                    "subsection_path": payload.get("subsection_path"),
                    "source_url": payload.get("source_url"),
                },
            ))

        elapsed = time.perf_counter() - start
        retrieval_latency_seconds.labels(mode="federal").observe(elapsed)
        logger.info(f"Federal retrieval: {len(chunks)} results in {elapsed:.3f}s")
        return chunks


class DocumentRetriever:
    """Retrieves evidence ONLY from a specific uploaded document in Qdrant.
    
    Strictly scoped to a single upload_id. Never accesses federal corpus.
    """

    def __init__(self, qdrant_client=None, embedding_fn=None):
        self.qdrant_client = qdrant_client
        self.embedding_fn = embedding_fn
        self.collection = settings.qdrant_document_collection

    def retrieve(
        self,
        query: str,
        upload_id: str,
        top_k: int = 10,
        score_threshold: float = 0.0,
    ) -> list[RetrievedChunk]:
        """Search ONLY within the specified upload_id's chunks."""
        start = time.perf_counter()
        retrieval_requests_total.labels(mode="document").inc()
        retrieval_by_mode_total.labels(mode="document").inc()

        if self.qdrant_client is None or self.embedding_fn is None:
            logger.warning("Document retriever not configured — returning empty results")
            return []

        try:
            query_embedding = self.embedding_fn([query])[0]
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return []

        # CRITICAL: Filter by upload_id to enforce isolation
        from qdrant_client.models import FieldCondition, Filter, MatchValue
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="upload_id",
                    match=MatchValue(value=upload_id),
                )
            ]
        )

        try:
            results = self.qdrant_client.search(
                collection_name=self.collection,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=top_k,
                score_threshold=score_threshold,
            )
        except Exception as e:
            logger.error(f"Qdrant search error: {e}")
            return []

        chunks = []
        for hit in results:
            payload = hit.payload or {}
            chunks.append(RetrievedChunk(
                chunk_id=str(hit.id),
                text=payload.get("text", ""),
                score=hit.score,
                metadata={
                    "source_type": "document",
                    "upload_id": payload.get("upload_id"),
                    "file_name": payload.get("file_name"),
                    "page_number": payload.get("page_number"),
                    "heading": payload.get("heading"),
                    "section_label": payload.get("section_label"),
                    "clause_title": payload.get("clause_title"),
                    "chunk_index": payload.get("chunk_index"),
                },
            ))

        elapsed = time.perf_counter() - start
        retrieval_latency_seconds.labels(mode="document").observe(elapsed)
        logger.info(f"Document retrieval (upload={upload_id}): {len(chunks)} results in {elapsed:.3f}s")
        return chunks


def get_retriever(mode: str, qdrant_client=None, embedding_fn=None):
    """Factory to get the appropriate retriever by mode. Never mixes modes."""
    if mode == QueryMode.FEDERAL:
        return FederalRetriever(qdrant_client, embedding_fn)
    elif mode == QueryMode.DOCUMENT:
        return DocumentRetriever(qdrant_client, embedding_fn)
    else:
        raise ValueError(f"Invalid retrieval mode: {mode}. Must be 'federal' or 'document'.")
