# Legal Chatbot — Design Doc

A grounded Q&A system over (1) the U.S. federal legal corpus and (2) user-uploaded contracts/legal documents, with strict source isolation so the two modes never bleed into each other.

---

## 1. Problem & Goals

**Problem.** General LLMs hallucinate legal citations and mix unrelated sources. For legal Q&A this is unacceptable — a fabricated `8 U.S.C. § 1101(a)(15)(F)(i)` is worse than "I don't know."

**Goals:**
- **Grounded answers only** — every claim cited to retrieved evidence (no parametric knowledge).
- **Strict mode isolation** — a question about an uploaded NDA must never pull from Title 26; a federal-law question must never pull from someone else's uploaded doc.
- **Confidence transparency** — return `HIGH / MEDIUM / LOW / INSUFFICIENT` rather than pretending all answers are equal.
- **Free-tier deployable** — Render + Supabase + Qdrant Cloud, no paid infra required for demo.

---

## 2. High-Level Architecture

```
   ┌────────────┐   POST /chat            ┌────────────────────────┐
   │  Next.js   │ ──────────────────────► │  FastAPI  (uvicorn)    │
   │  frontend  │   POST /upload          │   /api/v1/chat,/upload │
   └────────────┘ ◄──────────────────────  └──────┬─────────────────┘
                                                  │
                                ┌─────────────────▼──────────────────┐
                                │  LangGraph agent (13 nodes)        │
                                │  classify → retrieve → answer →     │
                                │  verify → persist                  │
                                └──┬──────────────┬───────────────┬──┘
                                   │              │               │
                            ┌──────▼─────┐ ┌──────▼──────┐ ┌──────▼─────┐
                            │ Qdrant     │ │ OpenAI      │ │ Postgres   │
                            │ federal_   │ │ gpt-4o +    │ │ audit log  │
                            │ corpus +   │ │ text-embed- │ │ + sessions │
                            │ uploaded_  │ │ 3-small     │ │            │
                            │ documents  │ │             │ │            │
                            └────────────┘ └─────────────┘ └────────────┘

   Observability sidecar (docker-compose only):
   Prometheus ── Grafana ── Loki ── Promtail ── node/cadvisor/pg/redis exporters
```

---

## 3. Tech Stack & Why

### 3.1 Backend framework — **FastAPI**

[backend/app/main.py](backend/app/main.py), [requirements.txt](backend/requirements.txt)

| Considered | Verdict |
|---|---|
| **FastAPI** ✅ | Async-native (we await OpenAI + Qdrant), Pydantic v2 for request/response schemas matches our typed `ChatRequest`/`ChatResponse`, auto OpenAPI docs, first-class lifespan hooks for warm-up. |
| Flask | Sync-by-default; we'd bolt on `asgiref`. No native schema validation. |
| Django | Too heavy — we don't need ORM/admin/auth out of the box. |
| Express/Node | Would force splitting Python (LangChain, PyMuPDF, lxml) from the API. |

### 3.2 Agent orchestration — **LangGraph**

[backend/app/agents/__init__.py](backend/app/agents/__init__.py) — 13-node graph: `ingest_input → classify_mode → extract_entities → detect_title_hints → detect_document_scope → make_plan → route_to_retriever → retrieve_context → grade_retrieval → generate_answer → verify_answer → retry_or_finalize → persist_logs_and_metrics`.

| Considered | Verdict |
|---|---|
| **LangGraph** ✅ | Explicit state machine — each node mutates `GraphState`. Conditional edges (`retry_or_finalize`) give us a retry loop without spaghetti `if/else`. Easy to add a node (e.g. reranker) without refactoring. |
| LangChain `AgentExecutor` | Too magical — tool-calling loop, hard to enforce mode isolation. |
| Plain Python | Doable, but the verification-retry edge gets ugly. Loss of free observability hooks per node. |
| CrewAI / AutoGen | Multi-agent overhead for a single-user Q&A flow we don't need. |

### 3.3 Vector store — **Qdrant**

[backend/app/core/qdrant_client.py](backend/app/core/qdrant_client.py)

Two collections, both COSINE distance, 1536-dim:
- `federal_corpus` — payload-indexed on `title_number` (INTEGER) for fast title-scoped filtering (e.g. "only Title 11 chunks").
- `uploaded_documents` — payload-indexed on `upload_id` (KEYWORD) — **this index is the linchpin of multi-tenant isolation**.

| Considered | Verdict |
|---|---|
| **Qdrant** ✅ | Rust core (fast), native payload filtering with proper indexes (critical — without them HTTP 400 on filter queries, see commit b078a1c), free cloud tier, runs locally in Docker for dev. |
| Pinecone | Closed-source, no free local dev, more expensive at scale. |
| Weaviate | Heavier resource footprint, GraphQL-first API is awkward from Python. |
| pgvector | Tempting (one less service) but filter+ANN performance worse than Qdrant once collection grows past ~100K vectors. Title 26 (IRC) alone is 55 MB of XML. |
| Chroma | Great for prototyping, weaker for multi-tenant filtering and prod ops. |

### 3.4 LLM + embeddings — **OpenAI gpt-4o + text-embedding-3-small**

[backend/app/core/llm.py:91](backend/app/core/llm.py#L91), [backend/app/core/config.py:63](backend/app/core/config.py#L63)

- `gpt-4o`, `temperature=0.1`, `max_tokens=4096` — low temp because we want extractive, citation-faithful answers, not creativity.
- `text-embedding-3-small`, 1536 dims — best $/quality at our scale. The 3-large variant doubles cost for marginal recall gain on legal text.
- Retry: exponential backoff w/ jitter on `RateLimitError / APITimeout / APIConnection / InternalServerError`.

| Considered | Verdict |
|---|---|
| **OpenAI** ✅ | Strongest reasoning at low temp, mature SDK, batched embeddings (we batch 512 at a time, [llm.py:180](backend/app/core/llm.py#L180)). |
| Anthropic Claude | Equally good for reasoning; would add a second provider. Could swap behind same `chat_completion()` interface — we kept that boundary clean. |
| Open-source (Llama 3, Mixtral via vLLM) | Cost-attractive but requires GPU infra; legal grounding quality lags at 7-70B sizes. |
| Cohere embeddings | Strong, but adds a vendor. OpenAI 1536-dim is the de-facto Qdrant default. |

### 3.5 SQL — **Postgres 16 + SQLAlchemy 2 (async)** + Alembic

Stores conversations, messages, retrieval logs, answer logs, verification logs — the audit trail. Async driver `asyncpg` because every request already runs in the async event loop.

Free-tier prod uses **Supabase** (managed Postgres).

### 3.6 Document parsing — **PyMuPDF (primary) + pdfplumber (fallback) + python-docx**

[backend/app/document_ingestion/__init__.py:57](backend/app/document_ingestion/__init__.py#L57)

| Considered | Verdict |
|---|---|
| **PyMuPDF** ✅ | Fastest PDF text extraction in Python, gives us font sizes so we can detect headings (font > 14pt → likely a heading). |
| pdfplumber (fallback) | Slower but more forgiving on weird PDFs — used when PyMuPDF returns empty. |
| Unstructured.io | Adds a heavy dep tree and external service in some modes. Overkill for this corpus. |
| LlamaParse | Hosted, costs money, lock-in. |

For DOCX, `python-docx` reads paragraph styles so we can chunk on Heading 1/2/3 boundaries.

### 3.7 Federal corpus parser — **lxml on USLM XML**

[backend/app/ingestion/pipeline.py:95](backend/app/ingestion/pipeline.py#L95) — `parse_uslm_title()` walks the U.S. Code XML hierarchy (Title → Chapter → Subchapter → Part → Subpart → Section → Subsection). The data lives in [data/](data/) as `usc08.xml ... usc42.xml` (sizes from 4 MB Title 11 to 112 MB Title 42).

We chunk at the **section** level by default; oversize sections get split along subsection/paragraph boundaries. Every chunk carries `canonical_citation` (e.g. `8 U.S.C. § 1101`) — that's what the model is told to cite.

Why XML and not just scraping text: USLM is the official structured form. We get clean section numbers, headings, and parentage for free.

### 3.8 Frontend — **Next.js 14 (App Router) + React 18 + Tailwind**

[frontend/src/app/page.tsx](frontend/src/app/page.tsx), [frontend/package.json](frontend/package.json)

Two-pane layout: chat on the left, citations/document workspace on the right. Mode switch (Knowledge = federal, Analysis = document) in the sidebar.

| Considered | Verdict |
|---|---|
| **Next.js** ✅ | App Router for nested layouts, easy Render deploy, good DX with Tailwind. |
| Vite + React SPA | Lighter, but Next gives us better routing for future features (per-document URLs). |
| SvelteKit | Smaller ecosystem for the UI primitives we'd want. |

### 3.9 Infra & observability — **Docker Compose locally, Render in prod**

[infra/docker-compose.yml](infra/docker-compose.yml), [render.yaml](render.yaml)

Local: 15 services across `core`, `monitoring`, and `full` profiles — Postgres, Redis, Qdrant, backend, frontend, nginx, Prometheus, Grafana, Loki, Promtail, node-exporter, cadvisor, postgres-exporter, redis-exporter.

Prod: Render (free) for backend + frontend, Supabase (free) for Postgres, Qdrant Cloud (free) for vectors. No persistent disk required.

**Why Prometheus + Grafana + Loki?** Standard, free, well-documented. Custom metrics in [backend/app/core/llm.py](backend/app/core/llm.py): `llm_calls_total`, `llm_call_duration_seconds`, `llm_tokens_{prompt,completion}_total`, `llm_failures_total`, `retrieval_latency_seconds`, `verification_pass/fail_total`.

| Considered | Verdict |
|---|---|
| Datadog / New Relic | Excellent but paid. |
| OpenTelemetry collector | Would layer in if we needed traces across services; metrics-first was simpler. |

---

## 4. RAG Pipeline — the core mechanic

### 4.1 Ingestion

**Federal** ([ingestion/pipeline.py](backend/app/ingestion/pipeline.py)):
1. Parse USLM XML → list of section-level chunks with full provenance (`title_number`, `section_number`, `canonical_citation`, `heading`, hierarchy path).
2. Truncate to ~25k chars to stay under OpenAI's embedding input limit.
3. Embed in batches of 64; upsert to `federal_corpus` with full payload.

**Document** ([document_ingestion/__init__.py](backend/app/document_ingestion/__init__.py)):
1. Parse PDF/DOCX → list of `DocumentPage(page_number, text, headings)`.
2. Chunk with `max_chunk_chars=3000`, **page-aware** (chunks never cross page boundaries — preserves citation accuracy) and **heading-aware**.
3. Regex-detect "Section N", "Article X", "Clause N" to populate `section_label`.
4. Embed, upsert to `uploaded_documents` with `upload_id` payload.

**Chunk size rationale:** 3000 chars (~750 tokens) balances recall (smaller = more precise hits) vs. context coherence (larger = answer has surrounding context). Section-level for federal because U.S. Code sections are already the natural unit of reference.

### 4.2 Retrieval

[backend/app/retrieval/__init__.py](backend/app/retrieval/__init__.py) — two retrievers, one rule each:

- `FederalRetriever`: optional `title_filter` (e.g. `[11, 26]`) via `FieldCondition(MatchAny)` so a tax question doesn't pull bankruptcy.
- `DocumentRetriever`: **mandatory** `upload_id` `MatchValue` filter. There is no code path where a document retrieval runs without it. This is what makes multi-user isolation safe.

`top_k = 10`, score threshold `0.65` (applied in the grader, not the retriever — we want the grader to see borderline hits and decide).

### 4.3 Generation & verification

[backend/app/agents/__init__.py:415](backend/app/agents/__init__.py#L415) (`generate_answer`) and `:543` (`verify_answer`):

- System prompts differ by mode. Federal: cite `[X U.S.C. § Y]`; never fabricate. Document: cite `[Page X, Section Y]`; no external knowledge.
- Evidence is formatted with citation tags inline so the model sees what it's allowed to cite.
- Verification is two-stage:
  1. **Structural** — citations present? cited sources actually appear in retrieved chunks? mode isolation respected?
  2. **LLM-based** — second GPT call grades whether each claim is supported by evidence.
- One retry on verification failure, then return with downgraded confidence.

**Why a separate verify step instead of trusting the generator?** Even at temp=0.1 gpt-4o occasionally drifts. The verify cost (one extra short call) is cheap insurance and produces a logged audit trail in Postgres.

---

## 5. Key design decisions, condensed

| Decision | Choice | Why not the alternative |
|---|---|---|
| One collection or two | **Two** (federal + documents) | One collection with mode filter risks accidental leakage if a query forgets the filter. Two collections make leakage structurally impossible. |
| Mode classification | **Explicit node before retrieval** | Lets us reject ambiguous queries early; cheaper than retrieving twice. |
| Title hints | **Keyword → title number mapping** | A learned classifier needs labeled data we don't have; rule-based gets us 90% there with debuggable behavior. |
| Confidence scoring | **4-level enum, not a float** | UI can badge HIGH/MEDIUM/LOW intuitively; floats invite false precision. |
| Verification | **Structural + LLM check, with retry** | Either alone misses cases. Structural catches mode leakage; LLM catches unsupported claims. |
| Embeddings model | **text-embedding-3-small (1536d)** | 3-large doubles cost for ~3-5% recall on legal text — not worth it at this scale. |
| Async stack | **FastAPI + asyncpg + qdrant async** | OpenAI + Qdrant calls dominate latency; sync would block the event loop. |
| Document chunking | **Page-aware, 3k chars** | Crossing pages breaks citation provenance; 3k balances recall vs context. |
| Deployment | **Render free + Qdrant Cloud + Supabase** | AWS/GCP work but burn money to demo; everything here scales up without rewrite. |
| Audit log in Postgres | **Every query persisted** | Required for offline eval, regression hunting, and "why did it say that?" debugging. |

---

## 6. Skills demonstrated (interview framing)

- **RAG system design** end-to-end: ingestion, chunking strategy per source type, retrieval with payload filters, generation, verification.
- **Multi-tenancy & isolation** via vector store payload indexes + mandatory filters.
- **Agent orchestration** with explicit state machines (LangGraph) instead of black-box agent loops.
- **Async Python at the API layer** (FastAPI, asyncpg).
- **Production concerns**: retries with backoff, Prometheus metrics, structured logging via Loki, Alembic migrations, health checks.
- **Cost-aware choices**: free-tier prod stack, batched embeddings, cheaper embedding model, temp=0.1 to keep outputs short.
- **Domain modeling**: parsing USLM XML into a hierarchy that preserves canonical citation form.

---

## 7. Things you should be ready to defend in the interview

1. **"Why not just use a single Qdrant collection with a mode filter?"** — Defense above. Bring up that the `upload_id` payload index is required for prod (commit `b078a1c`); we hit HTTP 400s before adding it.
2. **"How do you prevent prompt injection in uploaded documents?"** — Honest answer: we don't yet. Mitigations: low temp, evidence is wrapped in clear delimiters, system prompt explicitly says "answer only from evidence". Next step would be a sanitization pass and an instruction-following classifier.
3. **"Why gpt-4o and not Claude or open-source?"** — Cost/quality at temp=0.1 for citation faithfulness. The `chat_completion()` interface is a thin wrapper so swapping providers is one file.
4. **"Scaling past free tier?"** — Postgres → managed Supabase plan; Qdrant → larger cluster + sharding by tenant; backend → multiple Render instances behind a load balancer; add Redis-backed cache for repeat queries.
5. **"How do you evaluate this?"** — Audit log in Postgres feeds an offline eval. We can replay queries, compare citations to ground truth, and track verification pass rate over time as a regression signal.

---

Files to read before the interview, in order: [backend/app/main.py](backend/app/main.py), [backend/app/api/routes.py](backend/app/api/routes.py), [backend/app/agents/__init__.py](backend/app/agents/__init__.py), [backend/app/retrieval/__init__.py](backend/app/retrieval/__init__.py), [backend/app/core/qdrant_client.py](backend/app/core/qdrant_client.py), [backend/app/ingestion/pipeline.py](backend/app/ingestion/pipeline.py), [infra/docker-compose.yml](infra/docker-compose.yml), [render.yaml](render.yaml).
