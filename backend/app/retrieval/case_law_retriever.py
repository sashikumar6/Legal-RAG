"""Case law retriever — searches the case_law_corpus Qdrant collection.

Mirrors the structure of CfrRetriever (retrieval/cfr_retriever.py) but
targets the case_law_corpus collection and returns judicial citations.

Citation format returned: "Smith v. Jones, 123 F.3d 456 (9th Cir. 2019)"
Collection: "case_law_corpus"
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


class CaseLawRetriever:
    """
    Retrieves evidence ONLY from the case law corpus (case_law_corpus collection).

    Never accesses federal_corpus, cfr_corpus, or uploaded_documents.
    Never falls back to model-only answers.
    """

    def __init__(self, qdrant_client=None, embedding_fn=None):
        self.qdrant_client = qdrant_client
        self.embedding_fn = embedding_fn
        self.collection = settings.qdrant_case_law_collection

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        title_filter: Optional[list[int]] = None,
        score_threshold: float = 0.0,
    ) -> list[RetrievedChunk]:
        """
        Search the case law corpus with hybrid dense+sparse retrieval and RRF fusion.

        Args:
            query: Natural language query
            top_k: Number of results to return
            title_filter: Restrict to opinions related to specific USC title numbers
            score_threshold: Minimum score to include a result

        Returns:
            List of RetrievedChunk with case_law source_type metadata
        """
        start = time.perf_counter()
        retrieval_requests_total.labels(mode="case_law").inc()
        retrieval_by_mode_total.labels(mode="case_law").inc()

        if self.qdrant_client is None or self.embedding_fn is None:
            logger.warning("Case law retriever not configured — returning empty results")
            return []

        try:
            query_embedding = self.embedding_fn([query])[0]
        except Exception as exc:
            logger.error(f"Case law retriever embedding error: {exc}")
            return []

        # Build Qdrant filter for USC title numbers
        search_filter = None
        if title_filter:
            from qdrant_client.models import FieldCondition, Filter, MatchAny
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="us_code_titles",
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
        except Exception as exc:
            logger.error(f"Case law dense search error: {exc}")
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
                    "source_type": "case_law",
                    "case_name": payload.get("case_name"),
                    "court": payload.get("court"),
                    "date_filed": payload.get("date_filed"),
                    "canonical_citation": payload.get("canonical_citation") or payload.get("citation"),
                    "docket_number": payload.get("docket_number"),
                    "us_code_titles": payload.get("us_code_titles", []),
                    "opinion_id": payload.get("opinion_id"),
                    "cluster_id": payload.get("cluster_id"),
                },
            ))

        elapsed = time.perf_counter() - start
        retrieval_latency_seconds.labels(mode="case_law").observe(elapsed)
        logger.info(f"Case law retrieval: {len(chunks)} results in {elapsed:.3f}s")
        return chunks
