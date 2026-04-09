"""Federal corpus ingestion pipeline.

Reads local USLM XML files, parses them into structured chunks,
embeds with OpenAI, and indexes into Qdrant for retrieval.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.config import TITLE_FILE_MAP, TITLE_NAME_MAP, settings
from app.ingestion import ParsedChunk, parse_all_titles, parse_uslm_title
from app.observability import corpus_documents_ingested_total

logger = logging.getLogger(__name__)


class FederalIngestionPipeline:
    """Orchestrates parsing, chunking, embedding, and indexing of federal corpus."""

    def __init__(self, qdrant_client=None, embedding_fn=None):
        self.qdrant_client = qdrant_client
        self.embedding_fn = embedding_fn
        self.base_path = Path(settings.federal_xml_base_path)

    def ensure_collection(self) -> None:
        """Create or verify the Qdrant collection for federal corpus."""
        if self.qdrant_client is None:
            logger.warning("No Qdrant client configured — skipping collection setup")
            return

        from qdrant_client.models import Distance, VectorParams

        collection_name = settings.qdrant_federal_collection
        try:
            self.qdrant_client.get_collection(collection_name)
            logger.info(f"Collection '{collection_name}' already exists")
        except Exception:
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=settings.embedding_dimensions,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Created collection '{collection_name}'")

    def _chunk_to_payload(self, chunk: ParsedChunk) -> dict:
        """Convert a ParsedChunk to a Qdrant payload dict."""
        return {
            "document_id": chunk.document_id,
            "corpus": chunk.corpus,
            "jurisdiction": chunk.jurisdiction,
            "title_number": chunk.title_number,
            "title_name": chunk.title_name,
            "chapter": chunk.chapter,
            "subchapter": chunk.subchapter,
            "part": chunk.part,
            "subpart": chunk.subpart,
            "section_number": chunk.section_number,
            "subsection_path": chunk.subsection_path,
            "heading": chunk.heading,
            "canonical_citation": chunk.canonical_citation,
            "source_title": chunk.source_title,
            "source_url": chunk.source_url,
            "release_point": chunk.release_point,
            "publication_version": chunk.publication_version,
            "chunk_index": chunk.chunk_index,
            "parent_chunk_id": chunk.parent_chunk_id,
            "text": chunk.text,
            "normalized_text": chunk.normalized_text,
            "text_hash": chunk.text_hash,
        }

    def ingest_title(self, title_number: int) -> int:
        """Ingest a single U.S. Code title. Returns number of chunks indexed."""
        filename = TITLE_FILE_MAP.get(title_number)
        if not filename:
            logger.error(f"No file mapping for Title {title_number}")
            return 0

        xml_path = self.base_path / filename
        if not xml_path.exists():
            logger.warning(f"XML file not found for Title {title_number}: {xml_path}")
            return 0

        logger.info(f"Starting ingestion of Title {title_number} from {xml_path}")
        start = time.time()

        chunks = parse_uslm_title(xml_path, title_number)
        if not chunks:
            logger.warning(f"No chunks parsed for Title {title_number}")
            return 0

        # Index into Qdrant with real embeddings
        indexed = 0
        if self.qdrant_client is not None and self.embedding_fn is not None:
            indexed = self._index_chunks(chunks)
        else:
            logger.warning(
                f"Title {title_number}: {len(chunks)} chunks parsed but NOT indexed "
                f"(Qdrant client={self.qdrant_client is not None}, "
                f"embedding_fn={self.embedding_fn is not None})"
            )

        elapsed = time.time() - start
        logger.info(
            f"Title {title_number}: parsed {len(chunks)} chunks, "
            f"indexed {indexed} in {elapsed:.1f}s"
        )
        corpus_documents_ingested_total.labels(title_number=str(title_number)).inc()
        return indexed or len(chunks)

    def _index_chunks(self, chunks: list[ParsedChunk], batch_size: int = 64) -> int:
        """Embed and upsert chunks into Qdrant. Returns count indexed."""
        from qdrant_client.models import PointStruct

        collection = settings.qdrant_federal_collection
        total_indexed = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            # Truncate text to roughly 25k chars (~6k tokens) to avoid OpenAI limit
            texts = [c.text[:25000] for c in batch]

            try:
                embeddings = self.embedding_fn(texts)
            except Exception as e:
                logger.error(f"Embedding error at batch {i // batch_size}: {e}")
                continue

            points = []
            for chunk, embedding in zip(batch, embeddings):
                point_id = str(uuid.uuid4())
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=self._chunk_to_payload(chunk),
                    )
                )

            try:
                self.qdrant_client.upsert(
                    collection_name=collection,
                    points=points,
                )
                total_indexed += len(points)
                logger.info(
                    f"  Indexed batch {i // batch_size + 1}: "
                    f"{total_indexed}/{len(chunks)} chunks"
                )
            except Exception as e:
                logger.error(f"Qdrant upsert error at batch {i // batch_size}: {e}")

        return total_indexed

    def ingest_all(self) -> dict[int, int]:
        """Ingest all configured U.S. Code titles. Returns {title: chunk_count}."""
        self.ensure_collection()
        results: dict[int, int] = {}
        for title_num in settings.federal_titles:
            count = self.ingest_title(title_num)
            results[title_num] = count
        return results


def run_ingestion(base_path: Optional[str] = None, qdrant_client=None, embedding_fn=None):
    """CLI entry point for running federal ingestion with real clients."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if base_path:
        settings.federal_xml_base_path = base_path

    pipeline = FederalIngestionPipeline(
        qdrant_client=qdrant_client,
        embedding_fn=embedding_fn,
    )
    return pipeline.ingest_all()


if __name__ == "__main__":
    from app.core.qdrant_client import create_qdrant_client, ensure_collections
    from app.core.llm import create_embedding_fn, check_openai_configured

    q_client = create_qdrant_client()
    if q_client:
        ensure_collections(q_client)

    emb_fn = None
    if check_openai_configured():
        emb_fn = create_embedding_fn()

    run_ingestion(qdrant_client=q_client, embedding_fn=emb_fn)
