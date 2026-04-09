# Architecture Documentation

## System Overview

The Dual-Mode Federal Law and Document AI Intake Agent is a production-grade system for AI-powered legal research with two strictly isolated modes:

1. **Federal Legal Knowledge Q&A** — retrieval-augmented generation over curated U.S. Code titles
2. **Legal Document Q&A** — upload-grounded Q&A over PDF/DOCX legal documents

## Core Architecture Principles

### Strict Mode Isolation

The system enforces a fundamental architectural constraint: **federal corpus evidence and uploaded document evidence are never mixed**.

- The `FederalRetriever` only queries the `federal_corpus` Qdrant collection
- The `DocumentRetriever` only queries the `uploaded_documents` collection, filtered by `upload_id`
- The `verify_answer` node checks every citation for mode violations
- Cross-mode citations cause verification failure
- No silent fallback to model-only answers

### Structure-Aware Chunking

Federal corpus chunking respects the hierarchy of the U.S. Code:
- **Title → Chapter → Subchapter → Part → Section → Subsection**
- Primary chunk unit is the **section** level
- Large sections are split by subsection/paragraph hierarchy
- Every chunk preserves its complete citation lineage
- Canonical citations (e.g., "8 U.S.C. § 1101") are computed and stored

### Agent Workflow

The LangGraph workflow has 13 nodes:

```
ingest_input → classify_mode → extract_entities → detect_title_hints →
detect_document_scope → make_plan → route_to_retriever → retrieve_context →
grade_retrieval → generate_answer → verify_answer → retry_or_finalize →
persist_logs_and_metrics
```

### Verification Pipeline

Every answer undergoes verification:
1. Check that citations exist
2. Check mode isolation (no cross-mode citations)
3. Check confidence threshold
4. Flag unsupported claims
5. Retry once within the same mode if verification fails
6. Return "insufficient evidence" if retries are exhausted

## Data Model

14 tables organized in layers:

| Layer | Tables |
|-------|--------|
| Users | users, sessions |
| Conversations | conversations, messages |
| Federal Corpus | corpus_documents, corpus_chunks |
| Uploaded Documents | uploaded_documents, document_chunks |
| Upload Management | upload_sessions |
| Ingestion | ingestion_runs |
| Audit | retrieval_logs, answer_logs, verification_logs, retry_logs |

## Federal Corpus Coverage

| Title | Subject | File |
|-------|---------|------|
| 8 | Aliens and Nationality | usc08.xml |
| 11 | Bankruptcy | usc11.xml |
| 15 | Commerce and Trade | usc15.xml |
| 18 | Crimes and Criminal Procedure | usc18.xml |
| 26 | Internal Revenue Code | usc26.xml |
| 28 | Judiciary and Judicial Procedure | usc28.xml |
| 29 | Labor | usc29.xml |
| 42 | The Public Health and Welfare | usc42.xml |
