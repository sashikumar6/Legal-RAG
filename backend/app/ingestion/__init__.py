"""Federal corpus XML/USLM parser for U.S. Code titles.

Parses USLM-format XML files preserving hierarchy, extracting canonical
citations, and producing structure-aware chunks at the section level.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lxml import etree

from app.core.config import TITLE_FILE_MAP, TITLE_NAME_MAP, settings

logger = logging.getLogger(__name__)

# USLM namespace
USLM_NS = "http://xml.house.gov/schemas/uslm/1.0"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"

NSMAP = {
    "uslm": USLM_NS,
    "dc": DC_NS,
    "dcterms": DCTERMS_NS,
}


@dataclass
class HierarchyContext:
    """Tracks the current position in the document hierarchy."""
    title_number: int = 0
    title_name: str = ""
    chapter: Optional[str] = None
    chapter_heading: Optional[str] = None
    subchapter: Optional[str] = None
    subchapter_heading: Optional[str] = None
    part: Optional[str] = None
    part_heading: Optional[str] = None
    subpart: Optional[str] = None
    subpart_heading: Optional[str] = None
    release_point: Optional[str] = None
    publication_version: Optional[str] = None


@dataclass
class ParsedChunk:
    """A structured chunk extracted from USLM XML."""
    document_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    corpus: str = "uscode"
    jurisdiction: str = "federal"
    title_number: int = 0
    title_name: str = ""
    chapter: Optional[str] = None
    subchapter: Optional[str] = None
    part: Optional[str] = None
    subpart: Optional[str] = None
    section_number: Optional[str] = None
    subsection_path: Optional[str] = None
    heading: Optional[str] = None
    canonical_citation: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    release_point: Optional[str] = None
    publication_version: Optional[str] = None
    chunk_index: int = 0
    parent_chunk_id: Optional[str] = None
    text: str = ""
    normalized_text: str = ""
    text_hash: str = ""


def _tag(ns: str, local: str) -> str:
    """Build a Clark-notation tag."""
    return f"{{{ns}}}{local}"


def _extract_text(element: etree._Element) -> str:
    """Recursively extract all text content from an element, skipping TOC and notes."""
    if element is None:
        return ""

    tag_local = etree.QName(element.tag).localname if isinstance(element.tag, str) else ""

    # Skip table-of-contents and notes
    if tag_local in ("toc", "notes", "note", "meta"):
        return ""

    parts: list[str] = []
    if element.text:
        parts.append(element.text)
    for child in element:
        parts.append(_extract_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join(parts)


def _normalize_text(text: str) -> str:
    """Normalize whitespace and clean text."""
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


def _compute_hash(text: str) -> str:
    """Compute SHA-256 hash of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _get_num_value(element: etree._Element) -> Optional[str]:
    """Extract the value attribute from a <num> child."""
    num_el = element.find(_tag(USLM_NS, "num"))
    if num_el is not None:
        return num_el.get("value", num_el.text or "").strip()
    return None


def _get_heading_text(element: etree._Element) -> Optional[str]:
    """Extract heading text from a <heading> child."""
    heading_el = element.find(_tag(USLM_NS, "heading"))
    if heading_el is not None:
        return _normalize_text(_extract_text(heading_el))
    return None


def _build_canonical_citation(title_number: int, section_number: Optional[str]) -> Optional[str]:
    """Build a canonical citation string like '8 U.S.C. § 1101'."""
    if section_number:
        return f"{title_number} U.S.C. § {section_number}"
    return None


def _chunk_section(
    section_el: etree._Element,
    ctx: HierarchyContext,
    max_chunk_chars: int = 4000,
) -> list[ParsedChunk]:
    """
    Parse a <section> element into one or more chunks.
    
    Primary unit is section-level. If a section is too large,
    split by subsection/paragraph hierarchy without losing citation lineage.
    """
    section_number = _get_num_value(section_el)
    heading = _get_heading_text(section_el)
    identifier = section_el.get("identifier", "")

    # Check if section is repealed/omitted/transferred
    status = section_el.get("status", "")
    if status in ("repealed", "omitted", "transferred"):
        # Still index but mark in metadata
        pass

    full_text = _normalize_text(_extract_text(section_el))

    if not full_text or len(full_text) < 10:
        return []

    canonical = _build_canonical_citation(ctx.title_number, section_number)
    source_url = f"https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title{ctx.title_number}-section{section_number}&edition=prelim" if section_number else None

    parent_id = str(uuid.uuid4())

    # If section fits in one chunk, return as-is
    if len(full_text) <= max_chunk_chars:
        chunk = ParsedChunk(
            document_id=parent_id,
            title_number=ctx.title_number,
            title_name=ctx.title_name,
            chapter=ctx.chapter,
            subchapter=ctx.subchapter,
            part=ctx.part,
            subpart=ctx.subpart,
            section_number=section_number,
            heading=heading,
            canonical_citation=canonical,
            source_title=f"Title {ctx.title_number} - {ctx.title_name}",
            source_url=source_url,
            release_point=ctx.release_point,
            publication_version=ctx.publication_version,
            chunk_index=0,
            text=full_text,
            normalized_text=full_text.lower(),
            text_hash=_compute_hash(full_text),
        )
        return [chunk]

    # Split by subsection elements
    chunks: list[ParsedChunk] = []
    subsection_tags = [
        _tag(USLM_NS, "subsection"),
        _tag(USLM_NS, "paragraph"),
        _tag(USLM_NS, "subparagraph"),
    ]

    subsections = []
    for tag in subsection_tags:
        subsections = section_el.findall(f".//{tag}")
        if subsections:
            break

    if not subsections:
        # No subsections found — split by character boundary
        for i in range(0, len(full_text), max_chunk_chars):
            segment = full_text[i:i + max_chunk_chars]
            subsection_path = f"chunk-{i // max_chunk_chars}"
            chunk = ParsedChunk(
                document_id=str(uuid.uuid4()),
                title_number=ctx.title_number,
                title_name=ctx.title_name,
                chapter=ctx.chapter,
                subchapter=ctx.subchapter,
                part=ctx.part,
                subpart=ctx.subpart,
                section_number=section_number,
                subsection_path=subsection_path,
                heading=heading,
                canonical_citation=canonical,
                source_title=f"Title {ctx.title_number} - {ctx.title_name}",
                source_url=source_url,
                release_point=ctx.release_point,
                publication_version=ctx.publication_version,
                chunk_index=len(chunks),
                parent_chunk_id=parent_id,
                text=segment,
                normalized_text=segment.lower(),
                text_hash=_compute_hash(segment),
            )
            chunks.append(chunk)
        return chunks

    # Group subsections into chunks that respect max size
    current_text = ""
    current_path_parts: list[str] = []
    chunk_idx = 0

    for sub_el in subsections:
        sub_num = _get_num_value(sub_el) or ""
        sub_text = _normalize_text(_extract_text(sub_el))

        if not sub_text:
            continue

        if len(current_text) + len(sub_text) + 1 > max_chunk_chars and current_text:
            # Flush current chunk
            subsection_path = ", ".join(current_path_parts) if current_path_parts else None
            chunk = ParsedChunk(
                document_id=str(uuid.uuid4()),
                title_number=ctx.title_number,
                title_name=ctx.title_name,
                chapter=ctx.chapter,
                subchapter=ctx.subchapter,
                part=ctx.part,
                subpart=ctx.subpart,
                section_number=section_number,
                subsection_path=subsection_path,
                heading=heading,
                canonical_citation=f"{canonical}({subsection_path})" if canonical and subsection_path else canonical,
                source_title=f"Title {ctx.title_number} - {ctx.title_name}",
                source_url=source_url,
                release_point=ctx.release_point,
                publication_version=ctx.publication_version,
                chunk_index=chunk_idx,
                parent_chunk_id=parent_id,
                text=current_text.strip(),
                normalized_text=current_text.strip().lower(),
                text_hash=_compute_hash(current_text.strip()),
            )
            chunks.append(chunk)
            chunk_idx += 1
            current_text = ""
            current_path_parts = []

        current_text += " " + sub_text
        if sub_num:
            current_path_parts.append(sub_num)

    # Flush remaining
    if current_text.strip():
        subsection_path = ", ".join(current_path_parts) if current_path_parts else None
        chunk = ParsedChunk(
            document_id=str(uuid.uuid4()),
            title_number=ctx.title_number,
            title_name=ctx.title_name,
            chapter=ctx.chapter,
            subchapter=ctx.subchapter,
            part=ctx.part,
            subpart=ctx.subpart,
            section_number=section_number,
            subsection_path=subsection_path,
            heading=heading,
            canonical_citation=f"{canonical}({subsection_path})" if canonical and subsection_path else canonical,
            source_title=f"Title {ctx.title_number} - {ctx.title_name}",
            source_url=source_url,
            release_point=ctx.release_point,
            publication_version=ctx.publication_version,
            chunk_index=chunk_idx,
            parent_chunk_id=parent_id,
            text=current_text.strip(),
            normalized_text=current_text.strip().lower(),
            text_hash=_compute_hash(current_text.strip()),
        )
        chunks.append(chunk)

    return chunks


def parse_uslm_title(xml_path: Path, title_number: int) -> list[ParsedChunk]:
    """
    Parse a USLM XML file for a single U.S. Code title.
    
    Walks the hierarchy: title → chapter → subchapter → part → section
    and produces structure-aware chunks preserving citation lineage.
    """
    logger.info(f"Parsing Title {title_number} from {xml_path}")

    if not xml_path.exists():
        logger.warning(f"XML file not found: {xml_path}")
        return []

    try:
        tree = etree.parse(str(xml_path))
    except etree.XMLSyntaxError as e:
        logger.error(f"XML parse error for {xml_path}: {e}")
        return []

    root = tree.getroot()

    # Extract metadata
    meta_el = root.find(_tag(USLM_NS, "meta"))
    release_point = None
    pub_version = None
    if meta_el is not None:
        pub_name = meta_el.find(_tag(DC_NS, "title"))
        doc_pub = meta_el.findtext(_tag(USLM_NS, "docPublicationName"), default="")
        if doc_pub:
            release_point = doc_pub
            pub_version = doc_pub

    ctx = HierarchyContext(
        title_number=title_number,
        title_name=TITLE_NAME_MAP.get(title_number, f"Title {title_number}"),
        release_point=release_point,
        publication_version=pub_version,
    )

    all_chunks: list[ParsedChunk] = []
    section_tag = _tag(USLM_NS, "section")
    chapter_tag = _tag(USLM_NS, "chapter")
    subchapter_tag = _tag(USLM_NS, "subchapter")
    part_tag = _tag(USLM_NS, "part")
    subpart_tag = _tag(USLM_NS, "subpart")

    # Walk the main content
    main_el = root.find(_tag(USLM_NS, "main"))
    if main_el is None:
        logger.warning(f"No <main> element found in {xml_path}")
        return []

    title_el = main_el.find(_tag(USLM_NS, "title"))
    content_root = title_el if title_el is not None else main_el

    def _walk(element: etree._Element, depth: int = 0):
        """Recursively walk hierarchy, updating context."""
        tag = element.tag if isinstance(element.tag, str) else ""
        local = etree.QName(tag).localname if tag else ""

        if local == "chapter":
            ctx.chapter = _get_num_value(element)
            ctx.chapter_heading = _get_heading_text(element)
            ctx.subchapter = None
            ctx.part = None
            ctx.subpart = None
        elif local == "subchapter":
            ctx.subchapter = _get_num_value(element)
            ctx.subchapter_heading = _get_heading_text(element)
            ctx.part = None
            ctx.subpart = None
        elif local == "part":
            ctx.part = _get_num_value(element)
            ctx.part_heading = _get_heading_text(element)
            ctx.subpart = None
        elif local == "subpart":
            ctx.subpart = _get_num_value(element)

        if local == "section":
            chunks = _chunk_section(element, ctx)
            all_chunks.extend(chunks)
            return  # Don't recurse into section children

        for child in element:
            _walk(child, depth + 1)

    _walk(content_root)

    logger.info(f"Title {title_number}: parsed {len(all_chunks)} chunks")
    return all_chunks


def parse_all_titles(base_path: Optional[str] = None) -> dict[int, list[ParsedChunk]]:
    """
    Parse all configured U.S. Code titles from local XML files.
    
    Returns a dict mapping title_number → list of ParsedChunks.
    """
    base = Path(base_path) if base_path else Path(settings.federal_xml_base_path)
    results: dict[int, list[ParsedChunk]] = {}

    for title_num, filename in TITLE_FILE_MAP.items():
        xml_path = base / filename
        if not xml_path.exists():
            logger.warning(f"Missing XML file for Title {title_num}: {xml_path}")
            results[title_num] = []
            continue

        chunks = parse_uslm_title(xml_path, title_num)
        results[title_num] = chunks

    total = sum(len(c) for c in results.values())
    logger.info(f"Total chunks across all titles: {total}")
    return results
