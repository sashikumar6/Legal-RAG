"""Document ingestion module for PDF and DOCX uploads.

Provides page-aware, heading-aware chunking with upload-isolated indexing.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DocumentPage:
    """Represents a single page extracted from a document."""
    page_number: int
    text: str
    headings: list[str] = field(default_factory=list)


@dataclass
class DocumentChunkData:
    """A chunk extracted from an uploaded document."""
    document_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    upload_id: str = ""
    file_name: str = ""
    file_type: str = ""
    page_number: Optional[int] = None
    heading: Optional[str] = None
    section_label: Optional[str] = None
    clause_title: Optional[str] = None
    chunk_index: int = 0
    parent_chunk_id: Optional[str] = None
    text: str = ""
    normalized_text: str = ""
    text_hash: str = ""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# PDF parsing (PyMuPDF primary, pdfplumber fallback)
# ---------------------------------------------------------------------------

def parse_pdf_pymupdf(file_path: Path) -> list[DocumentPage]:
    """Parse PDF using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF not installed")
        return []

    pages: list[DocumentPage] = []
    try:
        doc = fitz.open(str(file_path))
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text.strip():
                # Extract headings by looking at font sizes
                headings = []
                blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE).get("blocks", [])
                for block in blocks:
                    if "lines" in block:
                        for line in block["lines"]:
                            for span in line.get("spans", []):
                                if span.get("size", 0) > 14 and span.get("text", "").strip():
                                    headings.append(span["text"].strip())

                pages.append(DocumentPage(
                    page_number=page_num + 1,
                    text=text,
                    headings=headings,
                ))
        doc.close()
    except Exception as e:
        logger.error(f"PyMuPDF parse error: {e}")

    return pages


def parse_pdf_pdfplumber(file_path: Path) -> list[DocumentPage]:
    """Fallback PDF parsing using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed")
        return []

    pages: list[DocumentPage] = []
    try:
        with pdfplumber.open(str(file_path)) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(DocumentPage(
                        page_number=i + 1,
                        text=text,
                    ))
    except Exception as e:
        logger.error(f"pdfplumber parse error: {e}")

    return pages


def parse_pdf(file_path: Path) -> list[DocumentPage]:
    """Parse PDF with PyMuPDF, falling back to pdfplumber."""
    pages = parse_pdf_pymupdf(file_path)
    if not pages:
        logger.info("PyMuPDF returned no pages, trying pdfplumber fallback")
        pages = parse_pdf_pdfplumber(file_path)
    return pages


# ---------------------------------------------------------------------------
# DOCX parsing
# ---------------------------------------------------------------------------

def parse_docx(file_path: Path) -> list[DocumentPage]:
    """Parse DOCX using python-docx. Groups content by headings."""
    try:
        from docx import Document as DocxDocument
    except ImportError:
        logger.error("python-docx not installed")
        return []

    pages: list[DocumentPage] = []
    try:
        doc = DocxDocument(str(file_path))
        current_heading: Optional[str] = None
        current_text_parts: list[str] = []
        page_counter = 1

        for para in doc.paragraphs:
            style_name = para.style.name if para.style else ""
            text = para.text.strip()

            if not text:
                continue

            if style_name.startswith("Heading"):
                # Flush previous section
                if current_text_parts:
                    pages.append(DocumentPage(
                        page_number=page_counter,
                        text="\n".join(current_text_parts),
                        headings=[current_heading] if current_heading else [],
                    ))
                    page_counter += 1
                    current_text_parts = []

                current_heading = text
                current_text_parts.append(text)
            else:
                current_text_parts.append(text)

        # Flush remaining
        if current_text_parts:
            pages.append(DocumentPage(
                page_number=page_counter,
                text="\n".join(current_text_parts),
                headings=[current_heading] if current_heading else [],
            ))

    except Exception as e:
        logger.error(f"DOCX parse error: {e}")

    return pages


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_document(
    pages: list[DocumentPage],
    upload_id: str,
    file_name: str,
    file_type: str,
    max_chunk_chars: int = 3000,
) -> list[DocumentChunkData]:
    """
    Chunk document pages into heading-aware, page-aware chunks.
    
    Does NOT blindly chunk by tokens. Respects page boundaries and
    heading structure.
    """
    chunks: list[DocumentChunkData] = []
    chunk_idx = 0
    parent_id = str(uuid.uuid4())

    for page in pages:
        text = _normalize(page.text)
        if not text:
            continue

        heading = page.headings[0] if page.headings else None

        # Detect section labels (e.g., "Section 1.", "Article II", "Clause 3")
        section_match = re.match(
            r"^(Section\s+\d+[\.\:]?|Article\s+[IVXLCDM\d]+[\.\:]?|Clause\s+\d+[\.\:]?)",
            text,
            re.IGNORECASE,
        )
        section_label = section_match.group(0).strip() if section_match else None

        if len(text) <= max_chunk_chars:
            chunks.append(DocumentChunkData(
                upload_id=upload_id,
                file_name=file_name,
                file_type=file_type,
                page_number=page.page_number,
                heading=heading,
                section_label=section_label,
                chunk_index=chunk_idx,
                parent_chunk_id=parent_id,
                text=text,
                normalized_text=text.lower(),
                text_hash=_hash(text),
            ))
            chunk_idx += 1
        else:
            # Split by paragraphs
            paragraphs = re.split(r"\n{2,}|(?<=\.)\s+(?=[A-Z])", text)
            current = ""
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                if len(current) + len(para) + 1 > max_chunk_chars and current:
                    chunks.append(DocumentChunkData(
                        upload_id=upload_id,
                        file_name=file_name,
                        file_type=file_type,
                        page_number=page.page_number,
                        heading=heading,
                        section_label=section_label,
                        chunk_index=chunk_idx,
                        parent_chunk_id=parent_id,
                        text=current.strip(),
                        normalized_text=current.strip().lower(),
                        text_hash=_hash(current.strip()),
                    ))
                    chunk_idx += 1
                    current = ""
                current += " " + para

            if current.strip():
                chunks.append(DocumentChunkData(
                    upload_id=upload_id,
                    file_name=file_name,
                    file_type=file_type,
                    page_number=page.page_number,
                    heading=heading,
                    section_label=section_label,
                    chunk_index=chunk_idx,
                    parent_chunk_id=parent_id,
                    text=current.strip(),
                    normalized_text=current.strip().lower(),
                    text_hash=_hash(current.strip()),
                ))
                chunk_idx += 1

    return chunks


def parse_and_chunk(
    file_path: Path,
    upload_id: str,
) -> list[DocumentChunkData]:
    """Parse a document file and return structured chunks."""
    suffix = file_path.suffix.lower()
    file_name = file_path.name
    file_type = suffix.lstrip(".")

    if suffix == ".pdf":
        pages = parse_pdf(file_path)
    elif suffix == ".docx":
        pages = parse_docx(file_path)
    else:
        logger.error(f"Unsupported file type: {suffix}")
        return []

    if not pages:
        logger.warning(f"No content extracted from {file_path}")
        return []

    chunks = chunk_document(pages, upload_id, file_name, file_type)
    logger.info(f"Document '{file_name}': {len(pages)} pages → {len(chunks)} chunks")
    return chunks
