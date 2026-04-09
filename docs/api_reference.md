# API Reference

## Base URL

```
http://localhost:8000/api/v1
```

## Endpoints

### POST /chat

Submit a query for AI-powered legal research.

**Request Body:**

```json
{
  "query": "What are the grounds for asylum under Title 8?",
  "session_id": "optional-session-id",
  "upload_id": "optional-upload-id-for-document-mode",
  "mode": "auto"  // "federal", "document", or "auto"
}
```

**Response:**

```json
{
  "answer": "Based on the retrieved evidence...",
  "mode": "federal",
  "confidence": "high",
  "citations": [
    {
      "source_type": "federal",
      "document_id": "chunk-uuid",
      "text": "The Attorney General may grant asylum...",
      "title_number": 8,
      "section_number": "1158",
      "canonical_citation": "8 U.S.C. § 1158",
      "relevance_score": 0.92
    }
  ],
  "clarification_needed": false,
  "disclaimer": "This information is for educational purposes only...",
  "session_id": "session-uuid",
  "message_id": "message-uuid",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### POST /upload

Upload a PDF or DOCX document for document-specific Q&A.

**Request:** Multipart form data with `file` field.

**Response:**

```json
{
  "upload_id": "upload-uuid",
  "file_name": "contract.pdf",
  "file_type": "pdf",
  "status": "completed",
  "chunk_count": 45,
  "message": "Document processed: 45 chunks indexed"
}
```

### POST /retrieval

Direct retrieval endpoint for testing.

**Request Body:**

```json
{
  "query": "bankruptcy filing",
  "mode": "federal",
  "top_k": 10,
  "title_filter": [11]
}
```

### GET /health

Overall health check. Returns `200 OK` with version and environment info.

### GET /health/live

Liveness probe. Returns `{"status": "alive"}`.

### GET /health/ready

Readiness probe. Checks database, Redis, and Qdrant connectivity.

### GET /metrics

Prometheus metrics endpoint. Returns all tracked metrics in Prometheus text format.
