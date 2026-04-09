"""Business logic services layer — wired to real Qdrant and OpenAI."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.schemas import (
    ChatRequest,
    ChatResponse,
    Citation,
    ConfidenceLevel,
    IngestionStatus,
    QueryMode,
    RetrievalRequest,
    RetrievalResponse,
    RetrievedChunk,
    UploadResponse,
)
from app.agents import build_agent_graph, GraphState
from app.retrieval import DocumentRetriever, FederalRetriever

logger = logging.getLogger(__name__)


class ChatService:
    """Orchestrates chat interactions through the LangGraph agent."""

    def __init__(self, qdrant_client=None, embedding_fn=None):
        self.qdrant_client = qdrant_client
        self.embedding_fn = embedding_fn
        self.federal_retriever = FederalRetriever(qdrant_client, embedding_fn)
        self.document_retriever = DocumentRetriever(qdrant_client, embedding_fn)
        self.agent_graph = build_agent_graph()

    async def process_query(self, request: ChatRequest) -> ChatResponse:
        """Process a chat query through the agent workflow."""
        session_id = request.session_id or str(uuid.uuid4())

        # Build initial state — inject retriever instances so the agent graph can use them
        initial_state: GraphState = {
            "query": request.query,
            "session_id": session_id,
            "upload_id": request.upload_id,
            "resolved_mode": request.mode if request.mode != QueryMode.AUTO else None,
            "needs_clarification": False,
            "entities": [],
            "title_hints": [],
            "retrieved_chunks": [],
            "citations": [],
            "verification_issues": [],
            "retrieval_retry_count": 0,
            "generation_retry_count": 0,
            "retrieval_score": 0.0,
            "retrieval_sufficient": False,
            "verification_passed": False,
            "confidence": ConfidenceLevel.INSUFFICIENT,
            # Inject live retriever instances so retrieve_context node can use them
            "federal_retriever": self.federal_retriever,
            "document_retriever": self.document_retriever,
        }

        # Run agent graph
        if self.agent_graph:
            try:
                final_state = self.agent_graph.invoke(initial_state)
            except Exception as e:
                logger.error(f"Agent graph error: {e}")
                final_state = initial_state
                final_state["error"] = str(e)
        else:
            # Graph not available — run nodes manually (same flow)
            from app.agents import (
                classify_mode, extract_entities, detect_title_hints,
                detect_document_scope, make_plan, grade_retrieval,
                generate_answer, verify_answer, retry_or_finalize,
                persist_logs_and_metrics,
            )
            state = initial_state
            if not state.get("resolved_mode"):
                state = classify_mode(state)
            state = extract_entities(state)
            state = detect_title_hints(state)
            state = detect_document_scope(state)
            state = make_plan(state)
            state = grade_retrieval(state)
            state = generate_answer(state)
            state = verify_answer(state)
            state = retry_or_finalize(state)
            state = persist_logs_and_metrics(state)
            final_state = state

        # Handle clarification
        if final_state.get("needs_clarification"):
            return ChatResponse(
                answer="",
                mode=final_state.get("resolved_mode", "auto"),
                confidence=ConfidenceLevel.INSUFFICIENT,
                clarification_needed=True,
                clarification_question=final_state.get("clarification_question", ""),
                session_id=session_id,
            )

        # Build response
        citations = []
        for cit_data in final_state.get("citations", []):
            citations.append(Citation(
                source_type=cit_data.get("source_type", ""),
                document_id=cit_data.get("document_id", ""),
                text=cit_data.get("text", ""),
                title_number=cit_data.get("title_number"),
                section_number=cit_data.get("section_number"),
                canonical_citation=cit_data.get("canonical_citation"),
                page_number=cit_data.get("page_number"),
                heading=cit_data.get("heading"),
                section_label=cit_data.get("section_label"),
                relevance_score=cit_data.get("relevance_score"),
            ))

        return ChatResponse(
            answer=final_state.get("final_answer") or final_state.get("draft_answer") or "Unable to generate answer.",
            mode=final_state.get("resolved_mode", "unknown"),
            confidence=ConfidenceLevel(final_state.get("confidence", ConfidenceLevel.INSUFFICIENT)),
            confidence_score=final_state.get("retrieval_score", 0.0),
            citations=citations,
            session_id=session_id,
        )


class UploadService:
    """Handles document uploads — parses, chunks, embeds, and indexes into Qdrant."""

    def __init__(self, qdrant_client=None, embedding_fn=None):
        self.qdrant_client = qdrant_client
        self.embedding_fn = embedding_fn
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def process_upload(
        self,
        file_name: str,
        file_content: bytes,
        file_type: str,
    ) -> UploadResponse:
        """Save, parse, chunk, embed, and index an uploaded document."""
        upload_id = str(uuid.uuid4())

        # Save file
        safe_name = f"{upload_id}_{file_name}"
        file_path = self.upload_dir / safe_name
        file_path.write_bytes(file_content)

        # Parse and chunk
        from app.document_ingestion import parse_and_chunk
        chunks = parse_and_chunk(file_path, upload_id)

        if not chunks:
            return UploadResponse(
                upload_id=upload_id,
                file_name=file_name,
                file_type=file_type,
                status=IngestionStatus.FAILED,
                message="Failed to extract content from document",
            )

        # Index into Qdrant with real embeddings
        indexed_count = 0
        if self.qdrant_client is not None and self.embedding_fn is not None:
            indexed_count = self._index_document_chunks(chunks, upload_id)
        else:
            logger.warning(
                "Qdrant client or embedding function not configured. "
                "Document chunks parsed but NOT indexed for vector search."
            )

        return UploadResponse(
            upload_id=upload_id,
            file_name=file_name,
            file_type=file_type,
            status=IngestionStatus.COMPLETED,
            chunk_count=len(chunks),
            message=f"Document processed: {len(chunks)} chunks parsed, {indexed_count} indexed",
        )

    def _index_document_chunks(self, chunks, upload_id: str) -> int:
        """Embed and index document chunks into Qdrant. Returns count indexed."""
        from qdrant_client.models import PointStruct

        collection = settings.qdrant_document_collection
        batch_size = 100
        total_indexed = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.text[:25000] for c in batch]

            try:
                embeddings = self.embedding_fn(texts)
            except Exception as e:
                logger.error(f"Embedding error during document indexing: {e}")
                continue

            points = []
            for chunk, embedding in zip(batch, embeddings):
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "document_id": chunk.document_id,
                        "upload_id": chunk.upload_id,
                        "file_name": chunk.file_name,
                        "file_type": chunk.file_type,
                        "page_number": chunk.page_number,
                        "heading": chunk.heading,
                        "section_label": chunk.section_label,
                        "clause_title": chunk.clause_title,
                        "chunk_index": chunk.chunk_index,
                        "text": chunk.text,
                        "normalized_text": chunk.normalized_text,
                        "text_hash": chunk.text_hash,
                    },
                ))

            try:
                self.qdrant_client.upsert(
                    collection_name=collection,
                    points=points,
                )
                total_indexed += len(points)
            except Exception as e:
                logger.error(f"Qdrant upsert error: {e}")

        logger.info(f"Document {upload_id}: indexed {total_indexed} chunks into '{collection}'")
        return total_indexed


class RetrievalService:
    """Direct retrieval service for testing."""

    def __init__(self, qdrant_client=None, embedding_fn=None):
        self.federal_retriever = FederalRetriever(qdrant_client, embedding_fn)
        self.document_retriever = DocumentRetriever(qdrant_client, embedding_fn)

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        if request.mode == QueryMode.FEDERAL:
            chunks = self.federal_retriever.retrieve(
                query=request.query,
                top_k=request.top_k,
                title_filter=request.title_filter,
            )
        elif request.mode == QueryMode.DOCUMENT and request.upload_id:
            chunks = self.document_retriever.retrieve(
                query=request.query,
                upload_id=request.upload_id,
                top_k=request.top_k,
            )
        else:
            chunks = []

        return RetrievalResponse(
            chunks=chunks,
            mode=request.mode,
            query=request.query,
            total_results=len(chunks),
        )
