"""CFR retriever — searches the cfr_corpus Qdrant collection.

Mirrors the structure of FederalRetriever (retrieval/__init__.py) but
targets the cfr_corpus collection and returns CFR citations.

Citation format returned: "26 C.F.R. § 1.401(a)-1"
Collection: "cfr_corpus"
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from app.core.config import settings
from app.core.schemas import RetrievedChunk
from app.observability import retrieval_by_mode_total, retrieval_latency_seconds, retrieval_requests_total
from app.retrieval import _build_sparse_vector, _rrf_fuse

logger = logging.getLogger(__name__)


class CfrRetriever:
    """
    Retrieves evidence ONLY from the CFR corpus (cfr_corpus collection).

    Never accesses federal_corpus or uploaded_documents.
    Never falls back to model-only answers.
    """

    def __init__(self, qdrant_client=None, embedding_fn=None):
        self.qdrant_client = qdrant_client
        self.embedding_fn = embedding_fn
        self.collection = settings.qdrant_cfr_collection

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        title_filter: Optional[list[int]] = None,
        part_filter: Optional[list[str]] = None,
        score_threshold: float = 0.0,
    ) -> list[RetrievedChunk]:
        """
        Search the CFR corpus with hybrid dense+sparse retrieval and RRF fusion.

        Args:
            query: Natural language query
            top_k: Number of results to return
            title_filter: Restrict search to specific CFR title numbers (e.g., [26, 29])
            part_filter: Restrict to specific CFR parts (e.g., ["1", "301"])
            score_threshold: Minimum score to include a result

        Returns:
            List of RetrievedChunk with cfr source_type metadata
        """
        start = time.perf_counter()
        retrieval_requests_total.labels(mode="cfr").inc()
        retrieval_by_mode_total.labels(mode="cfr").inc()

        if self.qdrant_client is None or self.embedding_fn is None:
            logger.warning("CFR retriever not configured — returning empty results")
            return []

        try:
            query_embedding = self.embedding_fn([query])[0]
        except Exception as e:
            logger.error(f"CFR retriever embedding error: {e}")
            return []

        # Build Qdrant filter for title and/or part
        search_filter = None
        filter_conditions = []

        if title_filter:
            from qdrant_client.models import FieldCondition, MatchAny
            filter_conditions.append(
                FieldCondition(
                    key="title_number",
                    match=MatchAny(any=title_filter),
                )
            )

        if part_filter:
            from qdrant_client.models import FieldCondition, MatchAny
            filter_conditions.append(
                FieldCondition(
                    key="part",
                    match=MatchAny(any=part_filter),
                )
            )

        if filter_conditions:
            from qdrant_client.models import Filter
            search_filter = Filter(must=filter_conditions)

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
            logger.error(f"CFR dense search error: {e}")
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
                    "source_type": "cfr",
                    "title_number": payload.get("title_number"),
                    "title_name": payload.get("title_name"),
                    "chapter": payload.get("chapter"),
                    "subchapter": payload.get("subchapter"),
                    "part": payload.get("part"),
                    "part_heading": payload.get("part_heading"),
                    "subpart": payload.get("subpart"),
                    "section_number": payload.get("section_number"),
                    "canonical_citation": payload.get("canonical_citation"),
                    "heading": payload.get("heading"),
                    "cfr_year": payload.get("cfr_year"),
                    "source_url": payload.get("source_url"),
                },
            ))

        elapsed = time.perf_counter() - start
        retrieval_latency_seconds.labels(mode="cfr").observe(elapsed)
        logger.info(f"CFR retrieval: {len(chunks)} results in {elapsed:.3f}s")
        return chunks
