# Architecture Decision Records

This file captures significant design decisions made during the Legal RAG system build.

---

## ADR-001: LangGraph for Agent Workflow

**Status:** Accepted

**Context:** We need a multi-step reasoning workflow with conditional branching (retry, fallback, verify).

**Decision:** Use LangGraph StateGraph with explicit nodes and typed state.

**Consequences:** Clear node boundaries; observable state; easy to test nodes in isolation.

---

## ADR-002: Qdrant for Vector Storage

**Status:** Accepted

**Context:** Need a production-grade vector store with filtering support.

**Decision:** Qdrant with cosine distance and payload filters for title/section scoping.

**Consequences:** Supports filtered search without post-processing; runs locally via Docker.

---

## ADR-003: Strict Mode Isolation

**Status:** Accepted

**Context:** Federal and document retrievers must not cross-contaminate results.

**Decision:** Each retriever accesses exactly one Qdrant collection. Mode is enforced at the retriever level and re-verified in `verify_answer`.

**Consequences:** Slightly more code per retriever; eliminates a class of hallucination bugs.

---

## ADR-004: OpenAI text-embedding-3-small

**Status:** Accepted

**Context:** Need a cost-effective embedding model for 1536-d vectors.

**Decision:** `text-embedding-3-small` (1536 dimensions) via OpenAI API.

**Consequences:** Good quality/cost ratio; same model must be used at ingest and query time.

---

## ADR-005: Pydantic-Settings for Configuration

**Status:** Accepted

**Context:** Multiple deployment environments with different secrets.

**Decision:** `pydantic-settings` with `.env` file loading and type coercion.

**Consequences:** Type-safe config; easy override via environment variables.

---

## ADR-006: Prometheus Metrics per Retrieval Mode

**Status:** Accepted

**Context:** Need observability on retrieval quality broken down by mode.

**Decision:** `retrieval_requests_total`, `retrieval_by_mode_total`, `retrieval_latency_seconds` counters with mode label for each retriever.

**Consequences:** Per-mode dashboards; latency histograms per mode.

---

## ADR-007: Hybrid Dense+Sparse Retrieval with RRF

**Status:** Accepted

**Context:** Dense-only retrieval misses exact keyword matches (section numbers, statute citations).

**Decision:** Combine dense (OpenAI embeddings) and sparse (BM25-style SHA-256 token hashing) vectors using Reciprocal Rank Fusion (k=60). Graceful fallback to dense-only when sparse index not configured.

**Consequences:** Better recall for exact legal citations; zero new runtime dependencies (SHA-256 is stdlib).

---

## ADR-008: CourtListener REST API for Case Law

**Status:** Accepted

**Context:** Need a free, research-permitted source of federal judicial opinions for the case law corpus.

**Decision:** Use CourtListener REST API v4 (`https://www.courtlistener.com/api/rest/v4/opinions/`) with `precedential_status=Precedential` and `date_filed__gte=2000-01-01` filters. Authenticate via `Authorization: Token {COURTLISTENER_API_KEY}`. Rate-limit to 1 req/sec with exponential backoff on 429.

**Alternatives considered:**
- Google Scholar (no structured API)
- Caselaw Access Project (Harvard CAP — bulk download only, requires account approval)
- PACER (paid, complex auth)

**Consequences:** Free for research use; structured JSON responses; requires a CourtListener account token; cluster metadata requires a second API call per opinion.

---

## ADR-009: Explicit Conflict Detection, Never Silent Resolution

**Status:** Accepted

**Context:** CROSS_SOURCE mode merges federal statutes, CFR regulations, and case law. These sources can contradict each other (e.g., a statute says X is required; a regulation creates an exception; a court ruling overturns the regulation).

**Decision:** `SourceMerger` flags conflicts explicitly using a `conflicts` list in its return value. Agents surface all conflicts to the user with `⚠ Note: conflicting interpretations found between [source_a] and [source_b] on [topic].` Conflicts are never silently resolved by picking one source over another.

**Conflict detection method:** Two chunks from different `source_type` values with text cosine similarity > 0.70 where one chunk contains negation/exception language (`shall not`, `prohibited`, `notwithstanding`, `overruled`, etc.) and the other does not.

**Consequences:** Users see all detected tensions; system never silently picks a winner; false positives are possible but preferable to silent errors in a legal context.

---

## ADR-010: Cosine 0.95 Deduplication Threshold

**Status:** Accepted

**Context:** CROSS_SOURCE queries retrieve up to 3×top_k chunks before merging. Near-identical passages appear across sources (e.g., a statute quoted verbatim in a regulation preamble, or an opinion quoting the statute it construes).

**Decision:** Deduplicate using text cosine similarity of term-frequency vectors. Threshold: 0.95. When two chunks exceed the threshold, keep the one with the higher retrieval score (lower threshold = more aggressive dedup, higher threshold = more duplicates reach the LLM).

**Threshold rationale:** 0.95 is strict enough to catch verbatim or near-verbatim duplicates while preserving paraphrases from different sources that contain genuinely distinct perspectives. Lowering below 0.90 risks removing useful cross-source variation.

**Consequences:** Reduced context window usage in CROSS_SOURCE mode; O(n²) comparison acceptable for n ≤ 30 (typical retrieval set size).
