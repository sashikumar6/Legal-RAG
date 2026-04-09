"""Prometheus metrics wiring for observability.

Defines all application-level metrics exposed at /metrics.
Metrics are grouped by domain: HTTP, LLM, Retrieval, Verification,
Ingestion, Answer Quality, and Workers.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# HTTP Metrics
# ---------------------------------------------------------------------------

http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

active_requests = Gauge(
    "active_requests",
    "Number of active HTTP requests",
)

# ---------------------------------------------------------------------------
# LLM Metrics
# ---------------------------------------------------------------------------

llm_calls_total = Counter(
    "llm_calls_total",
    "Total number of LLM API calls",
    ["model", "operation"],
)

llm_call_duration_seconds = Histogram(
    "llm_call_duration_seconds",
    "LLM API call duration in seconds",
    ["model", "operation"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0],
)

llm_retry_total = Counter(
    "llm_retry_total",
    "Total number of LLM API retries",
    ["model", "operation"],
)

llm_failures_total = Counter(
    "llm_failures_total",
    "Total number of LLM API failures",
    ["model", "error_type"],
)

llm_tokens_prompt_total = Counter(
    "llm_tokens_prompt_total",
    "Total prompt tokens consumed by LLM calls",
    ["model"],
)

llm_tokens_completion_total = Counter(
    "llm_tokens_completion_total",
    "Total completion tokens consumed by LLM calls",
    ["model"],
)

# ---------------------------------------------------------------------------
# Retrieval Metrics
# ---------------------------------------------------------------------------

retrieval_requests_total = Counter(
    "retrieval_requests_total",
    "Total number of retrieval requests",
    ["mode"],
)

retrieval_latency_seconds = Histogram(
    "retrieval_latency_seconds",
    "Retrieval latency in seconds",
    ["mode"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

retrieval_by_mode_total = Counter(
    "retrieval_by_mode_total",
    "Total retrieval requests by mode",
    ["mode"],
)

retrieval_empty_results_total = Counter(
    "retrieval_empty_results_total",
    "Total number of retrieval requests returning zero results",
    ["mode"],
)

retrieval_verification_failures_total = Counter(
    "retrieval_verification_failures_total",
    "Total number of retrieval verification failures",
    ["mode"],
)

# ---------------------------------------------------------------------------
# Verification & Answer Quality Metrics
# ---------------------------------------------------------------------------

verification_pass_total = Counter(
    "verification_pass_total",
    "Total number of verification passes",
)

verification_fail_total = Counter(
    "verification_fail_total",
    "Total number of verification failures",
    ["reason"],
)

citation_missing_total = Counter(
    "citation_missing_total",
    "Total number of answers with missing citations",
)

low_confidence_answers_total = Counter(
    "low_confidence_answers_total",
    "Total number of answers flagged as low confidence",
)

fallback_answers_total = Counter(
    "fallback_answers_total",
    "Total number of fallback (insufficient evidence) answers served",
)

# ---------------------------------------------------------------------------
# Ingestion Metrics
# ---------------------------------------------------------------------------

documents_uploaded_total = Counter(
    "documents_uploaded_total",
    "Total number of documents uploaded",
    ["file_type"],
)

documents_parsed_total = Counter(
    "documents_parsed_total",
    "Total number of documents successfully parsed",
    ["file_type"],
)

document_parse_failures_total = Counter(
    "document_parse_failures_total",
    "Total number of document parse failures",
    ["file_type"],
)

corpus_documents_ingested_total = Counter(
    "corpus_documents_ingested_total",
    "Total number of corpus documents ingested",
    ["title_number"],
)

embedding_jobs_total = Counter(
    "embedding_jobs_total",
    "Total number of embedding jobs executed",
)

embedding_job_failures_total = Counter(
    "embedding_job_failures_total",
    "Total number of embedding job failures",
)

# ---------------------------------------------------------------------------
# Worker Metrics
# ---------------------------------------------------------------------------

celery_jobs_total = Counter(
    "celery_jobs_total",
    "Total number of Celery jobs executed",
    ["queue", "task_name"],
)

celery_job_failures_total = Counter(
    "celery_job_failures_total",
    "Total number of Celery job failures",
    ["queue", "task_name"],
)

dead_letter_queue_size = Gauge(
    "dead_letter_queue_size",
    "Current number of messages in the dead-letter queue",
)
