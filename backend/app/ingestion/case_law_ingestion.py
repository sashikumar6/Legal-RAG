"""Case law ingestion pipeline.

Fetches precedential federal opinions from CourtListener REST API v4, chunks
at paragraph boundaries with 512-token max per chunk, and indexes into Qdrant's
case_law_corpus collection.

API endpoint:  https://www.courtlistener.com/api/rest/v4/opinions/
Auth:          Authorization: Token {COURTLISTENER_API_KEY}
Filter params: precedential_status=Precedential, date_filed__gte=2000-01-01
Max per title: 500 opinions (paginated via `next` field)
Citation fmt:  "Smith v. Jones, 123 F.3d 456 (9th Cir. 2019)"
Collection:    "case_law_corpus"
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


_COURTLISTENER_BASE = "https://www.courtlistener.com/api/rest/v4"
_OPINIONS_ENDPOINT = f"{_COURTLISTENER_BASE}/opinions/"
_CLUSTERS_ENDPOINT = f"{_COURTLISTENER_BASE}/clusters/"

# ~4 characters per token; 512 tokens ≈ 2048 chars
_MAX_CHUNK_CHARS = 512 * 4

# US Code title number → search query for CourtListener
TITLE_SEARCH_QUERIES: dict[int, str] = {
    8: "immigration alien nationality",
    11: "bankruptcy debtor creditor",
    15: "antitrust commerce trade",
    18: "criminal fraud federal offense",
    26: "internal revenue tax deduction",
    28: "jurisdiction judicial procedure",
    29: "labor employment FLSA ERISA",
    42: "civil rights social security medicare",
}

# Keywords used to tag a chunk with the USC titles it references
_TITLE_DETECTION_KEYWORDS: dict[int, list[str]] = {
    8:  ["8 u.s.c", "8 u.s.c.", "immigration and nationality act", " ina "],
    11: ["11 u.s.c", "11 u.s.c.", "bankruptcy code"],
    15: ["15 u.s.c", "15 u.s.c.", "sherman act", "ftc act"],
    18: ["18 u.s.c", "18 u.s.c."],
    26: ["26 u.s.c", "26 u.s.c.", "internal revenue code", " irc ", "i.r.c."],
    28: ["28 u.s.c", "28 u.s.c."],
    29: ["29 u.s.c", "29 u.s.c.", " flsa ", " erisa "],
    42: ["42 u.s.c", "42 u.s.c.", "civil rights act", "social security act"],
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CaseLawChunk:
    """A structured chunk extracted from a CourtListener opinion."""
    document_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    corpus: str = "case_law"
    jurisdiction: str = "federal"
    case_name: Optional[str] = None
    court: Optional[str] = None
    date_filed: Optional[str] = None
    citation: Optional[str] = None
    docket_number: Optional[str] = None
    us_code_titles: list = field(default_factory=list)
    opinion_id: Optional[str] = None
    cluster_id: Optional[str] = None
    chunk_index: int = 0
    parent_chunk_id: Optional[str] = None
    text: str = ""
    normalized_text: str = ""
    text_hash: str = ""


# ---------------------------------------------------------------------------
# Citation builder
# ---------------------------------------------------------------------------

def _build_case_law_citation(
    case_name: Optional[str],
    volume: Optional[str],
    reporter: Optional[str],
    page: Optional[str],
    court: Optional[str],
    year: Optional[str],
) -> Optional[str]:
    """Build canonical citation: 'Smith v. Jones, 123 F.3d 456 (9th Cir. 2019)'."""
    if not case_name:
        return None
    parts = [case_name]
    if volume and reporter and page:
        parts.append(f", {volume} {reporter} {page}")
    if court or year:
        suffix = ", ".join(p for p in [court, year] if p)
        parts.append(f" ({suffix})")
    return "".join(parts)


def _detect_us_code_titles(text: str) -> list[int]:
    """Detect USC title numbers referenced in opinion text."""
    text_lower = text.lower()
    return [
        num for num, keywords in _TITLE_DETECTION_KEYWORDS.items()
        if any(kw in text_lower for kw in keywords)
    ]


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strip_html_tags(text: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", clean).strip()


# ---------------------------------------------------------------------------
# Opinion text parser
# ---------------------------------------------------------------------------

class CaseLawTextParser:
    """
    Parses CourtListener opinion JSON into CaseLawChunk objects.

    Mirrors CfrXmlParser structure. Splits text at paragraph boundaries,
    accumulating paragraphs up to _MAX_CHUNK_CHARS per chunk.
    """

    def parse_opinion(self, opinion: dict, cluster: dict) -> list[CaseLawChunk]:
        """Parse opinion + cluster metadata dicts into CaseLawChunk objects."""
        raw = opinion.get("plain_text") or opinion.get("html_with_citations") or ""
        if "<" in raw:
            raw = _strip_html_tags(raw)
        full_text = _normalize_text(raw)
        if not full_text or len(full_text) < 20:
            logger.debug(f"Skipping opinion {opinion.get('id')} — empty text")
            return []

        case_name = cluster.get("case_name") or cluster.get("case_name_full", "")
        date_filed = cluster.get("date_filed", "")
        court = cluster.get("court_id") or cluster.get("court", "")
        year = date_filed[:4] if date_filed else ""

        citations_list = cluster.get("citations") or []
        volume = reporter = page = None
        if citations_list:
            c = citations_list[0]
            volume = str(c.get("volume", "")) if c.get("volume") else None
            reporter = c.get("reporter") or None
            page = str(c.get("page", "")) if c.get("page") else None

        canonical_citation = _build_case_law_citation(
            case_name, volume, reporter, page, court, year
        )
        docket_number = cluster.get("docket_number") or ""
        opinion_id = str(opinion.get("id", ""))
        cluster_id = str(cluster.get("id", ""))
        us_code_titles = _detect_us_code_titles(full_text)
        parent_id = str(uuid.uuid4())

        paragraphs = re.split(r"\n{2,}", full_text)
        paragraphs = [_normalize_text(p) for p in paragraphs if p.strip()]
        if not paragraphs:
            paragraphs = [full_text]

        return self._split_by_paragraphs(
            paragraphs, case_name, court, date_filed, canonical_citation,
            docket_number, us_code_titles, opinion_id, cluster_id, parent_id,
        )

    def _split_by_paragraphs(
        self, paragraphs, case_name, court, date_filed, canonical_citation,
        docket_number, us_code_titles, opinion_id, cluster_id, parent_id,
    ) -> list[CaseLawChunk]:
        chunks: list[CaseLawChunk] = []
        current = ""
        idx = 0
        for para in paragraphs:
            if not para:
                continue
            if len(current) + len(para) + 1 > _MAX_CHUNK_CHARS and current:
                chunks.append(self._make_chunk(
                    current.strip(), case_name, court, date_filed,
                    canonical_citation, docket_number, us_code_titles,
                    opinion_id, cluster_id, idx, parent_id,
                ))
                idx += 1
                current = ""
            current += " " + para
        if current.strip():
            chunks.append(self._make_chunk(
                current.strip(), case_name, court, date_filed,
                canonical_citation, docket_number, us_code_titles,
                opinion_id, cluster_id, idx, parent_id,
            ))
        return chunks

    def _make_chunk(
        self, text, case_name, court, date_filed, canonical_citation,
        docket_number, us_code_titles, opinion_id, cluster_id,
        chunk_idx, parent_id,
    ) -> CaseLawChunk:
        return CaseLawChunk(
            document_id=str(uuid.uuid4()),
            case_name=case_name,
            court=court,
            date_filed=date_filed,
            citation=canonical_citation,
            docket_number=docket_number,
            us_code_titles=us_code_titles,
            opinion_id=opinion_id,
            cluster_id=cluster_id,
            chunk_index=chunk_idx,
            parent_chunk_id=parent_id,
            text=text,
            normalized_text=text.lower(),
            text_hash=_compute_hash(text),
        )


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------

class CaseLawFetcher:
    """
    Fetches federal opinions from CourtListener API with rate limiting and retries.

    Mirrors CfrDownloader structure. Enforces 1 req/sec between requests; handles
    HTTP 429 with exponential backoff. Paginates via the `next` field in responses.
    """

    def __init__(self, api_key: str, max_opinions_per_title: int = 500):
        self.api_key = api_key
        self.max_opinions_per_title = max_opinions_per_title
        self._last_request_time: float = 0.0

    def _headers(self) -> dict:
        h = {"Accept": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Token {self.api_key}"
        return h

    def _rate_limit(self) -> None:
        """Enforce 1 req/sec between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self._last_request_time = time.time()

    def _get_json(
        self,
        url: str,
        params: Optional[dict] = None,
        max_retries: int = 3,
    ) -> Optional[dict]:
        """GET a URL, returning parsed JSON with exponential backoff on 429."""
        import httpx

        for attempt in range(max_retries):
            self._rate_limit()
            try:
                with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                    resp = client.get(url, params=params, headers=self._headers())

                    if resp.status_code == 429:
                        backoff = 2 ** attempt
                        logger.warning(f"Rate limited (429) — waiting {backoff}s")
                        time.sleep(backoff)
                        continue

                    if resp.status_code == 404:
                        logger.debug(f"Not found: {url}")
                        return None

                    resp.raise_for_status()
                    return resp.json()

            except Exception as exc:
                logger.warning(f"Request error for {url} (attempt {attempt + 1}): {exc}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        logger.error(f"Failed to fetch {url} after {max_retries} attempts")
        return None

    def _fetch_cluster(self, cluster_id: str) -> Optional[dict]:
        return self._get_json(f"{_CLUSTERS_ENDPOINT}{cluster_id}/")

    def fetch_opinions_for_title(self, title_number: int) -> list[tuple[dict, dict]]:
        """
        Fetch up to max_opinions_per_title precedential opinions relevant to
        a U.S. Code title. Returns (opinion_dict, cluster_dict) pairs.
        """
        search_query = TITLE_SEARCH_QUERIES.get(title_number, "")
        logger.info(
            f"Fetching case law for USC Title {title_number} "
            f"(query={search_query!r}, max={self.max_opinions_per_title})"
        )

        params: dict = {
            "precedential_status": "Precedential",
            "date_filed__gte": "2000-01-01",
            "ordering": "-date_filed",
            "page_size": 20,
            "format": "json",
        }
        if search_query:
            params["search"] = search_query

        pairs: list[tuple[dict, dict]] = []
        url: Optional[str] = _OPINIONS_ENDPOINT

        while url and len(pairs) < self.max_opinions_per_title:
            data = self._get_json(url, params=params if url == _OPINIONS_ENDPOINT else None)
            if not data:
                break

            for opinion in data.get("results", []):
                if len(pairs) >= self.max_opinions_per_title:
                    break
                cluster_url = opinion.get("cluster")
                if not cluster_url:
                    continue
                cluster_id = cluster_url.rstrip("/").rsplit("/", 1)[-1]
                cluster = self._fetch_cluster(cluster_id)
                if not cluster:
                    continue
                pairs.append((opinion, cluster))
                logger.debug(
                    f"  Fetched opinion {opinion.get('id')} "
                    f"({cluster.get('case_name', 'unknown')})"
                )

            url = data.get("next")

        logger.info(f"USC Title {title_number}: {len(pairs)} opinions fetched")
        return pairs


# ---------------------------------------------------------------------------
# Ingestion pipeline
# ---------------------------------------------------------------------------

class CaseLawIngestionPipeline:
    """
    Orchestrates fetching, parsing, embedding, and indexing of case law corpus.

    Mirrors CfrIngestionPipeline structure but targets the case_law_corpus
    Qdrant collection, fetching from CourtListener instead of govinfo.gov.
    """

    def __init__(self, qdrant_client=None, embedding_fn=None):
        from app.core.config import settings
        self.qdrant_client = qdrant_client
        self.embedding_fn = embedding_fn
        self.collection = settings.qdrant_case_law_collection
        self.us_code_titles = list(TITLE_SEARCH_QUERIES.keys())
        self.max_opinions = settings.case_law_max_opinions_per_title
        self.fetcher = CaseLawFetcher(
            api_key=settings.courtlistener_api_key,
            max_opinions_per_title=self.max_opinions,
        )
        self.parser = CaseLawTextParser()

    def ensure_collection(self) -> None:
        """Create or verify the case_law_corpus Qdrant collection."""
        if self.qdrant_client is None:
            logger.warning("No Qdrant client — skipping case law collection setup")
            return

        from qdrant_client.models import Distance, VectorParams
        from app.core.config import settings

        try:
            self.qdrant_client.get_collection(self.collection)
            logger.info(f"Case law collection '{self.collection}' already exists")
        except Exception:
            self.qdrant_client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=settings.embedding_dimensions,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Created case law collection '{self.collection}'")

    def _chunk_to_payload(self, chunk: CaseLawChunk) -> dict:
        return {
            "document_id": chunk.document_id,
            "corpus": chunk.corpus,
            "jurisdiction": chunk.jurisdiction,
            "case_name": chunk.case_name,
            "court": chunk.court,
            "date_filed": chunk.date_filed,
            "citation": chunk.citation,
            "canonical_citation": chunk.citation,
            "docket_number": chunk.docket_number,
            "us_code_titles": chunk.us_code_titles,
            "opinion_id": chunk.opinion_id,
            "cluster_id": chunk.cluster_id,
            "chunk_index": chunk.chunk_index,
            "parent_chunk_id": chunk.parent_chunk_id,
            "text": chunk.text,
            "normalized_text": chunk.normalized_text,
            "text_hash": chunk.text_hash,
        }

    def ingest_title(self, title_number: int) -> int:
        """Fetch, parse, and index case law for one USC title."""
        start = time.time()
        logger.info(f"Starting case law ingestion for USC Title {title_number}")

        pairs = self.fetcher.fetch_opinions_for_title(title_number)
        if not pairs:
            logger.warning(f"No opinions fetched for USC Title {title_number}")
            return 0

        all_chunks: list[CaseLawChunk] = []
        for opinion, cluster in pairs:
            all_chunks.extend(self.parser.parse_opinion(opinion, cluster))

        if not all_chunks:
            logger.warning(f"No chunks parsed for USC Title {title_number}")
            return 0

        indexed = 0
        if self.qdrant_client is not None and self.embedding_fn is not None:
            indexed = self._index_chunks(all_chunks)
        else:
            logger.warning(
                f"USC Title {title_number}: {len(all_chunks)} chunks parsed but NOT indexed "
                f"(qdrant={self.qdrant_client is not None}, "
                f"embedding={self.embedding_fn is not None})"
            )

        elapsed = time.time() - start
        logger.info(
            f"USC Title {title_number}: {len(all_chunks)} chunks parsed, "
            f"{indexed or len(all_chunks)} total in {elapsed:.1f}s"
        )
        return indexed or len(all_chunks)

    def _index_chunks(self, chunks: list[CaseLawChunk], batch_size: int = 64) -> int:
        """Embed and upsert case law chunks into Qdrant. Returns count indexed."""
        from qdrant_client.models import PointStruct

        total = 0
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.text[:25000] for c in batch]
            try:
                embeddings = self.embedding_fn(texts)
            except Exception as exc:
                logger.error(f"Embedding error at batch {i // batch_size}: {exc}")
                continue

            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=emb,
                    payload=self._chunk_to_payload(chunk),
                )
                for chunk, emb in zip(batch, embeddings)
            ]
            try:
                self.qdrant_client.upsert(collection_name=self.collection, points=points)
                total += len(points)
                logger.info(
                    f"  Indexed batch {i // batch_size + 1}: "
                    f"{total}/{len(chunks)} chunks"
                )
            except Exception as exc:
                logger.error(f"Qdrant upsert error at batch {i // batch_size}: {exc}")

        return total

    def ingest_all(self) -> dict[int, int]:
        """Ingest case law for all configured USC titles. Returns {title: chunk_count}."""
        self.ensure_collection()
        return {title: self.ingest_title(title) for title in self.us_code_titles}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run_case_law_ingestion(
    titles: Optional[list[int]] = None,
    qdrant_client=None,
    embedding_fn=None,
) -> dict[int, int]:
    """CLI entry point for case law ingestion."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    pipeline = CaseLawIngestionPipeline(
        qdrant_client=qdrant_client,
        embedding_fn=embedding_fn,
    )
    if titles:
        pipeline.us_code_titles = titles
    return pipeline.ingest_all()


if __name__ == "__main__":
    import sys

    _titles = [int(t) for t in sys.argv[1:]] if len(sys.argv) > 1 else None

    _qdrant = None
    _embedding = None

    try:
        from app.core.config import settings as _s
        from qdrant_client import QdrantClient
        _qdrant = QdrantClient(host=_s.qdrant_host, port=_s.qdrant_port)
    except Exception as _e:
        print(f"Qdrant not available: {_e}")

    try:
        from app.core.llm import check_openai_configured, create_embedding_fn
        if check_openai_configured():
            _embedding = create_embedding_fn()
    except Exception as _e:
        print(f"Embedding not available: {_e}")

    _results = run_case_law_ingestion(
        titles=_titles,
        qdrant_client=_qdrant,
        embedding_fn=_embedding,
    )
    print(f"Ingestion complete: {_results}")
