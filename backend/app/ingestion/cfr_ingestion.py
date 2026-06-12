"""CFR ingestion pipeline.

Downloads CFR XML bulk data from govinfo.gov, parses title/part/section
structure, chunks at section boundaries, and indexes into Qdrant's
cfr_corpus collection.

govinfo.gov bulk data URL pattern:
  https://www.govinfo.gov/bulkdata/CFR/{year}/title-{num}/CFR-{year}-title{num}-vol{vol}.xml

The XML uses a tag-soup format derived from the original SGML source:
  <CFRDOC>
    <TITLE>
      <CHAPTER>
        <PART>
          <SECTION>
            <SECTNO>§ 1.401(a)-1</SECTNO>
            <SUBJECT>Section heading</SUBJECT>
            <P>Paragraph text...</P>
          </SECTION>
        </PART>
      </CHAPTER>
    </TITLE>
  </CFRDOC>

Citation format: "26 C.F.R. § 1.401(a)-1"
Qdrant collection: "cfr_corpus"
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# Govinfo.gov bulk data base URL
_GOVINFO_BASE = "https://www.govinfo.gov/bulkdata/CFR"

# CFR title number → human-readable name (for covered titles)
CFR_TITLE_NAME_MAP: dict[int, str] = {
    26: "Internal Revenue",
    29: "Labor",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CfrChunk:
    """A structured chunk extracted from CFR XML."""
    document_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    corpus: str = "cfr"
    jurisdiction: str = "federal"
    title_number: int = 0
    title_name: str = ""
    chapter: Optional[str] = None
    subchapter: Optional[str] = None
    part: Optional[str] = None
    part_heading: Optional[str] = None
    subpart: Optional[str] = None
    section_number: Optional[str] = None
    heading: Optional[str] = None
    canonical_citation: Optional[str] = None
    source_url: Optional[str] = None
    cfr_year: int = 0
    chunk_index: int = 0
    parent_chunk_id: Optional[str] = None
    text: str = ""
    normalized_text: str = ""
    text_hash: str = ""


# ---------------------------------------------------------------------------
# Citation builder
# ---------------------------------------------------------------------------

def _build_cfr_citation(title_number: int, section_number: Optional[str]) -> Optional[str]:
    """Build canonical CFR citation like '26 C.F.R. § 1.401(a)-1'."""
    if section_number:
        # Strip leading § if present in the raw section number
        sec = section_number.lstrip("§").strip()
        return f"{title_number} C.F.R. § {sec}"
    return None


def _cfr_source_url(title_number: int, section_number: Optional[str], year: int) -> Optional[str]:
    if not section_number:
        return None
    sec = section_number.lstrip("§").strip()
    return f"https://www.ecfr.gov/current/title-{title_number}/section-{sec}"


# ---------------------------------------------------------------------------
# Text utilities (mirrors ingestion/__init__.py helpers)
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_element_text(element) -> str:
    """Recursively collect all text from an lxml element, skipping irrelevant nodes."""
    from lxml import etree

    skip_tags = {"NOTE", "NOTES", "CITA", "FTREF", "SOURCE", "SECAUTH"}
    tag_local = etree.QName(element.tag).localname if isinstance(element.tag, str) else ""
    if tag_local in skip_tags:
        return ""

    parts: list[str] = []
    if element.text:
        parts.append(element.text)
    for child in element:
        parts.append(_extract_element_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# CFR XML parser
# ---------------------------------------------------------------------------

class CfrXmlParser:
    """
    Parses CFR XML bulk data from govinfo.gov into CfrChunk objects.

    Handles the tag-soup XML format used by govinfo.gov CFR files.
    Chunks at section boundaries; splits large sections by paragraph.
    """

    MAX_CHUNK_CHARS = 4000

    def __init__(self, title_number: int, cfr_year: int):
        self.title_number = title_number
        self.title_name = CFR_TITLE_NAME_MAP.get(title_number, f"Title {title_number}")
        self.cfr_year = cfr_year

    def parse_file(self, xml_path: Path) -> list[CfrChunk]:
        """Parse a single CFR XML volume file into chunks."""
        try:
            from lxml import etree
        except ImportError:
            logger.error("lxml is required for CFR parsing — install with: pip install lxml")
            return []

        if not xml_path.exists():
            logger.warning(f"CFR XML file not found: {xml_path}")
            return []

        logger.info(f"Parsing CFR Title {self.title_number} from {xml_path}")

        try:
            # CFR XML often has encoding issues; use recover=True
            parser = etree.XMLParser(recover=True, encoding="utf-8")
            try:
                tree = etree.parse(str(xml_path), parser)
            except Exception:
                # Try without explicit encoding (some files are ISO-8859-1)
                parser2 = etree.XMLParser(recover=True)
                tree = etree.parse(str(xml_path), parser2)
        except Exception as e:
            logger.error(f"Failed to parse {xml_path}: {e}")
            return []

        root = tree.getroot()
        all_chunks: list[CfrChunk] = []

        # Walk hierarchy: CHAPTER → SUBCHAP → PART → SUBPART → SECTION
        ctx = _CfrContext(
            title_number=self.title_number,
            title_name=self.title_name,
            cfr_year=self.cfr_year,
        )
        self._walk(root, ctx, all_chunks)

        logger.info(f"CFR Title {self.title_number}: parsed {len(all_chunks)} chunks from {xml_path.name}")
        return all_chunks

    def _walk(self, element, ctx: "_CfrContext", chunks: list[CfrChunk], depth: int = 0):
        """Recursively walk CFR XML hierarchy updating context."""
        from lxml import etree

        tag = etree.QName(element.tag).localname if isinstance(element.tag, str) else ""

        if tag == "CHAPTER":
            ctx.chapter = element.get("CHAPNUM") or self._find_child_text(element, "CHPTHD")
        elif tag == "SUBCHAP":
            ctx.subchapter = element.get("SCHAPNUM") or self._find_child_text(element, "SUBCHAPTHD")
        elif tag in ("PART", "SUBPART"):
            if tag == "PART":
                ctx.part = element.get("PARTNUM") or self._find_child_text(element, "EAR")
                ctx.part_heading = self._find_child_text(element, "PTHD") or self._find_child_text(element, "HD")
                ctx.subpart = None
            else:
                ctx.subpart = self._find_child_text(element, "SUBPTHD") or self._find_child_text(element, "HD")

        if tag == "SECTION":
            section_chunks = self._parse_section(element, ctx)
            chunks.extend(section_chunks)
            return  # Don't recurse into section children

        for child in element:
            self._walk(child, ctx, chunks, depth + 1)

    def _parse_section(self, section_el, ctx: "_CfrContext") -> list[CfrChunk]:
        """Parse a <SECTION> element into one or more CfrChunk objects."""
        from lxml import etree

        # Extract section number (SECTNO) and heading (SUBJECT or HD)
        sectno_el = section_el.find("SECTNO")
        subject_el = section_el.find("SUBJECT") or section_el.find("HD")

        raw_sectno = sectno_el.text.strip() if sectno_el is not None and sectno_el.text else None
        heading = subject_el.text.strip() if subject_el is not None and subject_el.text else None

        # Normalize section number: "§ 1.401(a)-1" → "1.401(a)-1"
        section_number = raw_sectno.lstrip("§").strip() if raw_sectno else None

        full_text = _normalize_text(_extract_element_text(section_el))
        if not full_text or len(full_text) < 10:
            return []

        canonical = _build_cfr_citation(ctx.title_number, section_number)
        source_url = _cfr_source_url(ctx.title_number, section_number, ctx.cfr_year)
        parent_id = str(uuid.uuid4())

        if len(full_text) <= self.MAX_CHUNK_CHARS:
            return [CfrChunk(
                document_id=parent_id,
                title_number=ctx.title_number,
                title_name=ctx.title_name,
                chapter=ctx.chapter,
                subchapter=ctx.subchapter,
                part=ctx.part,
                part_heading=ctx.part_heading,
                subpart=ctx.subpart,
                section_number=section_number,
                heading=heading,
                canonical_citation=canonical,
                source_url=source_url,
                cfr_year=ctx.cfr_year,
                chunk_index=0,
                text=full_text,
                normalized_text=full_text.lower(),
                text_hash=_compute_hash(full_text),
            )]

        # Split large sections by paragraph elements
        para_tags = {"P", "FP", "fp"}
        paragraphs = [
            child for child in section_el
            if etree.QName(child.tag).localname in para_tags
        ]

        if not paragraphs:
            # Fallback: split by character boundary
            return self._split_by_chars(full_text, section_number, heading, canonical, source_url, ctx, parent_id)

        return self._split_by_paragraphs(
            paragraphs, section_number, heading, canonical, source_url, ctx, parent_id
        )

    def _split_by_paragraphs(
        self, paragraphs, section_number, heading, canonical, source_url,
        ctx: "_CfrContext", parent_id: str
    ) -> list[CfrChunk]:
        chunks: list[CfrChunk] = []
        current_text = ""
        chunk_idx = 0

        for para in paragraphs:
            para_text = _normalize_text(_extract_element_text(para))
            if not para_text:
                continue

            if len(current_text) + len(para_text) + 1 > self.MAX_CHUNK_CHARS and current_text:
                chunks.append(self._make_chunk(
                    current_text.strip(), section_number, heading, canonical,
                    source_url, ctx, chunk_idx, parent_id
                ))
                chunk_idx += 1
                current_text = ""

            current_text += " " + para_text

        if current_text.strip():
            chunks.append(self._make_chunk(
                current_text.strip(), section_number, heading, canonical,
                source_url, ctx, chunk_idx, parent_id
            ))

        return chunks

    def _split_by_chars(
        self, text, section_number, heading, canonical, source_url,
        ctx: "_CfrContext", parent_id: str
    ) -> list[CfrChunk]:
        chunks = []
        for i in range(0, len(text), self.MAX_CHUNK_CHARS):
            segment = text[i:i + self.MAX_CHUNK_CHARS]
            chunks.append(self._make_chunk(
                segment, section_number, heading, canonical,
                source_url, ctx, i // self.MAX_CHUNK_CHARS, parent_id
            ))
        return chunks

    def _make_chunk(
        self, text, section_number, heading, canonical, source_url,
        ctx: "_CfrContext", chunk_idx: int, parent_id: str
    ) -> CfrChunk:
        return CfrChunk(
            document_id=str(uuid.uuid4()),
            title_number=ctx.title_number,
            title_name=ctx.title_name,
            chapter=ctx.chapter,
            subchapter=ctx.subchapter,
            part=ctx.part,
            part_heading=ctx.part_heading,
            subpart=ctx.subpart,
            section_number=section_number,
            heading=heading,
            canonical_citation=canonical,
            source_url=source_url,
            cfr_year=ctx.cfr_year,
            chunk_index=chunk_idx,
            parent_chunk_id=parent_id,
            text=text,
            normalized_text=text.lower(),
            text_hash=_compute_hash(text),
        )

    @staticmethod
    def _find_child_text(element, tag: str) -> Optional[str]:
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        return None


@dataclass
class _CfrContext:
    """Mutable hierarchy context while walking CFR XML."""
    title_number: int
    title_name: str
    cfr_year: int
    chapter: Optional[str] = None
    subchapter: Optional[str] = None
    part: Optional[str] = None
    part_heading: Optional[str] = None
    subpart: Optional[str] = None


# ---------------------------------------------------------------------------
# Downloader
# ---------------------------------------------------------------------------

class CfrDownloader:
    """
    Downloads CFR XML bulk data files from govinfo.gov with caching and retries.

    The index at https://www.govinfo.gov/bulkdata/CFR/{year}/title-{num}/
    lists available volume files. We fetch the listing, extract .xml URLs,
    and download each one.
    """

    def __init__(self, download_dir: str, year: int):
        self.download_dir = Path(download_dir)
        self.year = year
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def get_volume_urls(self, title_number: int) -> list[str]:
        """Fetch the govinfo.gov listing and extract CFR XML volume URLs."""
        import httpx

        index_url = f"{_GOVINFO_BASE}/{self.year}/title-{title_number}/"
        logger.info(f"Fetching CFR Title {title_number} index from {index_url}")

        urls: list[str] = []
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                resp = client.get(index_url)
                resp.raise_for_status()
                content = resp.text

            # Parse XML sitemap format
            if "<loc>" in content or "sitemap" in content.lower():
                urls = re.findall(r"<loc>(https?://[^<]+\.xml)</loc>", content)

            # Fall back: look for href links in HTML listing
            if not urls:
                urls = re.findall(
                    rf'href="(CFR-{self.year}-title{title_number}-vol\d+\.xml)"',
                    content,
                )
                urls = [urljoin(index_url, u) for u in urls]

            # Last resort: construct known URL pattern for volumes 1–20
            if not urls:
                logger.warning(
                    f"Could not parse index for Title {title_number}; "
                    "falling back to probing volumes 1–20"
                )
                urls = [
                    f"{_GOVINFO_BASE}/{self.year}/title-{title_number}/"
                    f"CFR-{self.year}-title{title_number}-vol{v}.xml"
                    for v in range(1, 21)
                ]

        except Exception as e:
            logger.error(f"Failed to fetch CFR index for Title {title_number}: {e}")
            # Still try the known pattern as a fallback
            urls = [
                f"{_GOVINFO_BASE}/{self.year}/title-{title_number}/"
                f"CFR-{self.year}-title{title_number}-vol{v}.xml"
                for v in range(1, 21)
            ]

        return urls

    def download_volume(
        self,
        url: str,
        title_number: int,
        volume: int,
        max_retries: int = 3,
    ) -> Optional[Path]:
        """Download one CFR volume XML file, returning the local path. Returns None on failure."""
        import httpx

        filename = f"CFR-{self.year}-title{title_number}-vol{volume}.xml"
        dest = self.download_dir / filename

        if dest.exists() and dest.stat().st_size > 1000:
            logger.info(f"Using cached {filename}")
            return dest

        for attempt in range(max_retries):
            try:
                logger.info(f"Downloading {url} (attempt {attempt + 1})")
                with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                    resp = client.get(url)
                    if resp.status_code == 404:
                        logger.debug(f"Volume {volume} not found (404) — skipping")
                        return None
                    resp.raise_for_status()

                dest.write_bytes(resp.content)
                logger.info(f"Downloaded {filename} ({len(resp.content) // 1024} KB)")
                return dest

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None  # Volume doesn't exist
                logger.warning(f"HTTP error downloading {url}: {e}")
            except Exception as e:
                logger.warning(f"Download error for {url}: {e}")

            if attempt < max_retries - 1:
                backoff = 2 ** attempt
                logger.info(f"Retrying in {backoff}s...")
                time.sleep(backoff)

        logger.error(f"Failed to download {url} after {max_retries} attempts")
        return None

    def download_title(self, title_number: int) -> list[Path]:
        """Download all volumes for a CFR title. Returns list of local paths."""
        volume_urls = self.get_volume_urls(title_number)
        local_paths: list[Path] = []

        for i, url in enumerate(volume_urls, start=1):
            path = self.download_volume(url, title_number, volume=i)
            if path is not None:
                local_paths.append(path)

        logger.info(f"Downloaded {len(local_paths)} volumes for CFR Title {title_number}")
        return local_paths


# ---------------------------------------------------------------------------
# Ingestion pipeline
# ---------------------------------------------------------------------------

class CfrIngestionPipeline:
    """
    Orchestrates downloading, parsing, embedding, and indexing of CFR corpus.

    Mirrors the structure of FederalIngestionPipeline (backend/app/ingestion/pipeline.py)
    but targets the cfr_corpus Qdrant collection.
    """

    def __init__(self, qdrant_client=None, embedding_fn=None):
        from app.core.config import settings
        self.qdrant_client = qdrant_client
        self.embedding_fn = embedding_fn
        self.collection = settings.qdrant_cfr_collection
        self.cfr_titles = settings.cfr_titles
        self.download_dir = settings.cfr_download_dir
        self.cfr_year = settings.cfr_year
        self.downloader = CfrDownloader(self.download_dir, self.cfr_year)

    def ensure_collection(self) -> None:
        """Create or verify the cfr_corpus Qdrant collection."""
        from app.core.config import settings

        if self.qdrant_client is None:
            logger.warning("No Qdrant client configured — skipping CFR collection setup")
            return

        from qdrant_client.models import Distance, VectorParams

        try:
            self.qdrant_client.get_collection(self.collection)
            logger.info(f"CFR collection '{self.collection}' already exists")
        except Exception:
            self.qdrant_client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=settings.embedding_dimensions,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Created CFR collection '{self.collection}'")

    def _chunk_to_payload(self, chunk: CfrChunk) -> dict:
        return {
            "document_id": chunk.document_id,
            "corpus": chunk.corpus,
            "jurisdiction": chunk.jurisdiction,
            "title_number": chunk.title_number,
            "title_name": chunk.title_name,
            "chapter": chunk.chapter,
            "subchapter": chunk.subchapter,
            "part": chunk.part,
            "part_heading": chunk.part_heading,
            "subpart": chunk.subpart,
            "section_number": chunk.section_number,
            "heading": chunk.heading,
            "canonical_citation": chunk.canonical_citation,
            "source_url": chunk.source_url,
            "cfr_year": chunk.cfr_year,
            "chunk_index": chunk.chunk_index,
            "parent_chunk_id": chunk.parent_chunk_id,
            "text": chunk.text,
            "normalized_text": chunk.normalized_text,
            "text_hash": chunk.text_hash,
        }

    def ingest_title(self, title_number: int) -> int:
        """Download, parse, and index all CFR volumes for one title."""
        start = time.time()
        logger.info(f"Starting CFR Title {title_number} ingestion")

        volume_paths = self.downloader.download_title(title_number)
        if not volume_paths:
            logger.warning(f"No CFR XML files downloaded for Title {title_number}")
            return 0

        parser = CfrXmlParser(title_number, self.cfr_year)
        all_chunks: list[CfrChunk] = []

        for vol_path in volume_paths:
            chunks = parser.parse_file(vol_path)
            all_chunks.extend(chunks)

        if not all_chunks:
            logger.warning(f"No chunks parsed for CFR Title {title_number}")
            return 0

        indexed = 0
        if self.qdrant_client is not None and self.embedding_fn is not None:
            indexed = self._index_chunks(all_chunks)
        else:
            logger.warning(
                f"CFR Title {title_number}: {len(all_chunks)} chunks parsed but NOT indexed "
                f"(Qdrant={self.qdrant_client is not None}, "
                f"embedding={self.embedding_fn is not None})"
            )

        elapsed = time.time() - start
        logger.info(
            f"CFR Title {title_number}: {len(all_chunks)} chunks parsed, "
            f"{indexed} indexed in {elapsed:.1f}s"
        )
        return indexed or len(all_chunks)

    def _index_chunks(self, chunks: list[CfrChunk], batch_size: int = 64) -> int:
        """Embed and upsert CFR chunks into Qdrant. Returns count indexed."""
        from qdrant_client.models import PointStruct

        total_indexed = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.text[:25000] for c in batch]

            try:
                embeddings = self.embedding_fn(texts)
            except Exception as e:
                logger.error(f"Embedding error at batch {i // batch_size}: {e}")
                continue

            points = []
            for chunk, embedding in zip(batch, embeddings):
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload=self._chunk_to_payload(chunk),
                ))

            try:
                self.qdrant_client.upsert(
                    collection_name=self.collection,
                    points=points,
                )
                total_indexed += len(points)
                logger.info(
                    f"  Indexed CFR batch {i // batch_size + 1}: "
                    f"{total_indexed}/{len(chunks)} chunks"
                )
            except Exception as e:
                logger.error(f"Qdrant upsert error at batch {i // batch_size}: {e}")

        return total_indexed

    def ingest_all(self) -> dict[int, int]:
        """Ingest all configured CFR titles. Returns {title: chunk_count}."""
        self.ensure_collection()
        results: dict[int, int] = {}
        for title_num in self.cfr_titles:
            count = self.ingest_title(title_num)
            results[title_num] = count
        return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run_cfr_ingestion(
    titles: Optional[list[int]] = None,
    qdrant_client=None,
    embedding_fn=None,
) -> dict[int, int]:
    """CLI entry point for CFR ingestion."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    pipeline = CfrIngestionPipeline(
        qdrant_client=qdrant_client,
        embedding_fn=embedding_fn,
    )

    if titles:
        pipeline.cfr_titles = titles

    return pipeline.ingest_all()


if __name__ == "__main__":
    from app.core.qdrant_client import create_qdrant_client, ensure_collections
    from app.core.llm import create_embedding_fn, check_openai_configured

    q_client = create_qdrant_client()
    emb_fn = None
    if check_openai_configured():
        emb_fn = create_embedding_fn()

    run_cfr_ingestion(qdrant_client=q_client, embedding_fn=emb_fn)
