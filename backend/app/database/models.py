"""SQLAlchemy ORM models for the application."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Users & Sessions
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String(255), unique=True, nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_active_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata_ = Column("metadata", JSONB, default=dict)

    user = relationship("User", back_populates="sessions")
    conversations = relationship("Conversation", back_populates="session", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Conversations & Messages
# ---------------------------------------------------------------------------

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    title = Column(String(500), nullable=True)
    mode = Column(String(50), nullable=True)  # federal, document, or mixed
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("Session", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    role = Column(String(50), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    mode = Column(String(50), nullable=True)
    confidence = Column(String(50), nullable=True)
    citations = Column(JSONB, default=list)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )


# ---------------------------------------------------------------------------
# Federal Corpus
# ---------------------------------------------------------------------------

class CorpusDocument(Base):
    __tablename__ = "corpus_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corpus = Column(String(50), nullable=False, default="uscode")
    jurisdiction = Column(String(50), nullable=False, default="federal")
    title_number = Column(Integer, nullable=False)
    title_name = Column(String(500), nullable=False)
    source_file = Column(String(500), nullable=True)
    release_point = Column(String(100), nullable=True)
    publication_version = Column(String(100), nullable=True)
    total_chunks = Column(Integer, default=0)
    ingested_at = Column(DateTime, default=datetime.utcnow)
    metadata_ = Column("metadata", JSONB, default=dict)

    chunks = relationship("CorpusChunk", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_corpus_documents_title", "title_number"),
    )


class CorpusChunk(Base):
    __tablename__ = "corpus_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("corpus_documents.id"), nullable=False)
    corpus = Column(String(50), nullable=False, default="uscode")
    jurisdiction = Column(String(50), nullable=False, default="federal")
    title_number = Column(Integer, nullable=False)
    title_name = Column(String(500), nullable=True)
    chapter = Column(String(200), nullable=True)
    subchapter = Column(String(200), nullable=True)
    part = Column(String(200), nullable=True)
    subpart = Column(String(200), nullable=True)
    section_number = Column(String(100), nullable=True)
    subsection_path = Column(String(500), nullable=True)
    heading = Column(Text, nullable=True)
    canonical_citation = Column(String(500), nullable=True)
    source_url = Column(String(1000), nullable=True)
    chunk_index = Column(Integer, default=0)
    parent_chunk_id = Column(UUID(as_uuid=True), nullable=True)
    text = Column(Text, nullable=False)
    normalized_text = Column(Text, nullable=True)
    text_hash = Column(String(64), nullable=False)
    embedding_id = Column(String(255), nullable=True)  # Qdrant point ID
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("CorpusDocument", back_populates="chunks")

    __table_args__ = (
        Index("ix_corpus_chunks_title_section", "title_number", "section_number"),
        Index("ix_corpus_chunks_citation", "canonical_citation"),
        Index("ix_corpus_chunks_hash", "text_hash"),
    )


# ---------------------------------------------------------------------------
# Uploaded Documents
# ---------------------------------------------------------------------------

class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    upload_id = Column(String(255), unique=True, nullable=False)
    file_name = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    file_path = Column(String(1000), nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    total_chunks = Column(Integer, default=0)
    total_pages = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_uploaded_documents_upload_id", "upload_id"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("uploaded_documents.id"), nullable=False)
    upload_id = Column(String(255), nullable=False)
    file_name = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    page_number = Column(Integer, nullable=True)
    heading = Column(Text, nullable=True)
    section_label = Column(String(200), nullable=True)
    clause_title = Column(String(500), nullable=True)
    chunk_index = Column(Integer, default=0)
    parent_chunk_id = Column(UUID(as_uuid=True), nullable=True)
    text = Column(Text, nullable=False)
    normalized_text = Column(Text, nullable=True)
    text_hash = Column(String(64), nullable=False)
    embedding_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("UploadedDocument", back_populates="chunks")

    __table_args__ = (
        Index("ix_document_chunks_upload_id", "upload_id"),
        Index("ix_document_chunks_page", "upload_id", "page_number"),
    )


# ---------------------------------------------------------------------------
# Upload Sessions
# ---------------------------------------------------------------------------

class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=True)
    upload_id = Column(String(255), nullable=False)
    file_name = Column(String(500), nullable=False)
    status = Column(String(50), nullable=False, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Ingestion Runs
# ---------------------------------------------------------------------------

class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_type = Column(String(50), nullable=False)  # federal, document
    source = Column(String(500), nullable=True)
    status = Column(String(50), nullable=False, default="started")
    total_documents = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    errors = Column(JSONB, default=list)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)


# ---------------------------------------------------------------------------
# Logging Models
# ---------------------------------------------------------------------------

class RetrievalLog(Base):
    __tablename__ = "retrieval_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), nullable=True)
    mode = Column(String(50), nullable=False)
    query = Column(Text, nullable=False)
    top_k = Column(Integer, nullable=True)
    results_count = Column(Integer, default=0)
    avg_score = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=True)
    title_filter = Column(JSONB, nullable=True)
    upload_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AnswerLog(Base):
    __tablename__ = "answer_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), nullable=True)
    mode = Column(String(50), nullable=False)
    query = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    confidence = Column(String(50), nullable=True)
    citations_count = Column(Integer, default=0)
    llm_model = Column(String(100), nullable=True)
    llm_tokens_used = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class VerificationLog(Base):
    __tablename__ = "verification_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), nullable=True)
    passed = Column(Boolean, nullable=False)
    issues = Column(JSONB, default=list)
    unsupported_claims = Column(JSONB, default=list)
    mode_violation = Column(Boolean, default=False)
    confidence_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RetryLog(Base):
    __tablename__ = "retry_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), nullable=True)
    retry_type = Column(String(50), nullable=False)  # retrieval, generation
    retry_count = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    outcome = Column(String(50), nullable=True)  # success, exhausted
    created_at = Column(DateTime, default=datetime.utcnow)
