"""Isolated retrieval layer — strictly separates federal and document retrieval."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any, Optional

from app.core.config import settings
from app.core.schemas import QueryMode, RetrievedChunk
from app.observability import retrieval_by_mode_total, retrieval_latency_seconds, retrieval_requests_total

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hybrid search helpers (shared by FederalRetriever and CfrRetriever)
# ---------------------------------------------------------------------------

def _build_sparse_vector(text: str) -> tuple[list[int], list[float]]:
    """Convert query text to a token-frequency sparse vector for Qdrant sparse search.

    Maps each token to a bucket in a 2^17-dimensional space via SHA-256 hashing.
    Returns empty lists when text contains no alphanumeric tokens.
    """
    tokens = re.findall(r'\b[a-z0-9]+\b', text.lower())
    if not tokens:
        return [], []

    freq: dict[int, int] = {}
    for token in tokens:
        idx = int(hashlib.sha256(token.encode()).hexdigest(), 16) % 131072
        freq[idx] = freq.get(idx, 0) + 1

    n = len(tokens)
    indices = sorted(freq.keys())
    values = [freq[i] / n for i in indices]
    return indices, values


def _rrf_fuse(
    dense_hits: list,
    sparse_hits: list,
    k: int = 60,
    top_k: int = 10,
) -> list:
    """Reciprocal Rank Fusion of dense and sparse result lists.

    Returns a list of hits ordered by descending RRF score, truncated to top_k.
    """
    scores: dict[str, float] = {}
    hit_by_id: dict[str, Any] = {}

    for rank, hit in enumerate(dense_hits):
        hid = str(hit.id)
        scores[hid] = scores.get(hid, 0.0) + 1.0 / (k + rank + 1)
        hit_by_id[hid] = hit

    for rank, hit in enumerate(sparse_hits):
        hid = str(hit.id)
        scores[hid] = scores.get(hid, 0.0) + 1.0 / (k + rank + 1)
        if hid not in hit_by_id:
            hit_by_id[hid] = hit

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [hit_by_id[hid] for hid, _ in ranked]


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
        """Search the federal corpus with hybrid dense+sparse retrieval and RRF fusion."""
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

        # Dense search (fetch 2× for RRF headroom)
        try:
            dense_results = self.qdrant_client.search(
                collection_name=self.collection,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=top_k * 2,
                score_threshold=0.0,
            )
        except Exception as e:
            logger.error(f"Qdrant dense search error: {e}")
            return []

        # Sparse search — graceful fallback if collection has no sparse index
        sparse_results: list = []
        try:
            from qdrant_client.models import SparseVector
            s_indices, s_values = _build_sparse_vector(query)
            if s_indices:
                sparse_results = self.qdrant_client.search(
                    collection_name=self.collection,
                    query_vector=("sparse", SparseVector(indices=s_indices, values=s_values)),
                    query_filter=search_filter,
                    limit=top_k * 2,
                    score_threshold=0.0,
                )
        except Exception:
            pass  # dense-only when sparse vectors are not indexed

        # RRF fusion then score-threshold filter
        fused = _rrf_fuse(dense_results, sparse_results, top_k=top_k)
        results = [h for h in fused if h.score >= score_threshold]

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
