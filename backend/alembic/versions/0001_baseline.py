"""baseline: create all tables

Revision ID: 0001_baseline
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("external_id", sa.String(255), unique=True, nullable=True),
        sa.Column("email", sa.String(255), unique=True, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime),
    )

    # Sessions
    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("last_active_at", sa.DateTime),
        sa.Column("metadata", JSONB, default={}),
    )

    # Conversations
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("mode", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime),
    )

    # Messages
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("mode", sa.String(50), nullable=True),
        sa.Column("confidence", sa.String(50), nullable=True),
        sa.Column("citations", JSONB, default=[]),
        sa.Column("metadata", JSONB, default={}),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"])

    # Corpus Documents
    op.create_table(
        "corpus_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("corpus", sa.String(50), nullable=False),
        sa.Column("jurisdiction", sa.String(50), nullable=False),
        sa.Column("title_number", sa.Integer, nullable=False),
        sa.Column("title_name", sa.String(500), nullable=False),
        sa.Column("source_file", sa.String(500), nullable=True),
        sa.Column("release_point", sa.String(100), nullable=True),
        sa.Column("publication_version", sa.String(100), nullable=True),
        sa.Column("total_chunks", sa.Integer, default=0),
        sa.Column("ingested_at", sa.DateTime),
        sa.Column("metadata", JSONB, default={}),
    )
    op.create_index("ix_corpus_documents_title", "corpus_documents", ["title_number"])

    # Corpus Chunks
    op.create_table(
        "corpus_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("corpus_documents.id"), nullable=False),
        sa.Column("corpus", sa.String(50), nullable=False),
        sa.Column("jurisdiction", sa.String(50), nullable=False),
        sa.Column("title_number", sa.Integer, nullable=False),
        sa.Column("title_name", sa.String(500), nullable=True),
        sa.Column("chapter", sa.String(200), nullable=True),
        sa.Column("subchapter", sa.String(200), nullable=True),
        sa.Column("part", sa.String(200), nullable=True),
        sa.Column("subpart", sa.String(200), nullable=True),
        sa.Column("section_number", sa.String(100), nullable=True),
        sa.Column("subsection_path", sa.String(500), nullable=True),
        sa.Column("heading", sa.Text, nullable=True),
        sa.Column("canonical_citation", sa.String(500), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("chunk_index", sa.Integer, default=0),
        sa.Column("parent_chunk_id", UUID(as_uuid=True), nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("normalized_text", sa.Text, nullable=True),
        sa.Column("text_hash", sa.String(64), nullable=False),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime),
    )
    op.create_index("ix_corpus_chunks_title_section", "corpus_chunks", ["title_number", "section_number"])
    op.create_index("ix_corpus_chunks_citation", "corpus_chunks", ["canonical_citation"])
    op.create_index("ix_corpus_chunks_hash", "corpus_chunks", ["text_hash"])

    # Uploaded Documents
    op.create_table(
        "uploaded_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("upload_id", sa.String(255), unique=True, nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("total_chunks", sa.Integer, default=0),
        sa.Column("total_pages", sa.Integer, nullable=True),
        sa.Column("uploaded_at", sa.DateTime),
        sa.Column("processed_at", sa.DateTime, nullable=True),
        sa.Column("metadata", JSONB, default={}),
    )
    op.create_index("ix_uploaded_documents_upload_id", "uploaded_documents", ["upload_id"])

    # Document Chunks
    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("uploaded_documents.id"), nullable=False),
        sa.Column("upload_id", sa.String(255), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("heading", sa.Text, nullable=True),
        sa.Column("section_label", sa.String(200), nullable=True),
        sa.Column("clause_title", sa.String(500), nullable=True),
        sa.Column("chunk_index", sa.Integer, default=0),
        sa.Column("parent_chunk_id", UUID(as_uuid=True), nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("normalized_text", sa.Text, nullable=True),
        sa.Column("text_hash", sa.String(64), nullable=False),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime),
    )
    op.create_index("ix_document_chunks_upload_id", "document_chunks", ["upload_id"])
    op.create_index("ix_document_chunks_page", "document_chunks", ["upload_id", "page_number"])

    # Upload Sessions
    op.create_table(
        "upload_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("sessions.id"), nullable=True),
        sa.Column("upload_id", sa.String(255), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("expires_at", sa.DateTime, nullable=True),
    )

    # Ingestion Runs
    op.create_table(
        "ingestion_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_type", sa.String(50), nullable=False),
        sa.Column("source", sa.String(500), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("total_documents", sa.Integer, default=0),
        sa.Column("total_chunks", sa.Integer, default=0),
        sa.Column("errors", JSONB, default=[]),
        sa.Column("started_at", sa.DateTime),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("metadata", JSONB, default={}),
    )

    # Retrieval Logs
    op.create_table(
        "retrieval_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", UUID(as_uuid=True), nullable=True),
        sa.Column("mode", sa.String(50), nullable=False),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("top_k", sa.Integer, nullable=True),
        sa.Column("results_count", sa.Integer, default=0),
        sa.Column("avg_score", sa.Float, nullable=True),
        sa.Column("latency_ms", sa.Float, nullable=True),
        sa.Column("title_filter", JSONB, nullable=True),
        sa.Column("upload_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime),
    )

    # Answer Logs
    op.create_table(
        "answer_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", UUID(as_uuid=True), nullable=True),
        sa.Column("mode", sa.String(50), nullable=False),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=True),
        sa.Column("confidence", sa.String(50), nullable=True),
        sa.Column("citations_count", sa.Integer, default=0),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("llm_tokens_used", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime),
    )

    # Verification Logs
    op.create_table(
        "verification_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", UUID(as_uuid=True), nullable=True),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("issues", JSONB, default=[]),
        sa.Column("unsupported_claims", JSONB, default=[]),
        sa.Column("mode_violation", sa.Boolean, default=False),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime),
    )

    # Retry Logs
    op.create_table(
        "retry_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", UUID(as_uuid=True), nullable=True),
        sa.Column("retry_type", sa.String(50), nullable=False),
        sa.Column("retry_count", sa.Integer, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("outcome", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime),
    )


def downgrade() -> None:
    op.drop_table("retry_logs")
    op.drop_table("verification_logs")
    op.drop_table("answer_logs")
    op.drop_table("retrieval_logs")
    op.drop_table("ingestion_runs")
    op.drop_table("upload_sessions")
    op.drop_table("document_chunks")
    op.drop_table("uploaded_documents")
    op.drop_table("corpus_chunks")
    op.drop_table("corpus_documents")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("sessions")
    op.drop_table("users")
