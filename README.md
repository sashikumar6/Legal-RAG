# Federal Law RAG

Federal Law RAG is a production-grade retrieval-augmented generation system for U.S. federal legal research. It combines hybrid dense+sparse retrieval (BM25-style SHA-256 hashing + OpenAI embeddings, fused via Reciprocal Rank Fusion) across four strictly isolated Qdrant collections — federal statutes, CFR regulations, federal case law, and uploaded documents — with a 13-node LangGraph workflow for classification, grounding, verification, and answer generation. Cross-source queries run all three law corpora through a `SourceMerger` that deduplicates near-identical passages (cosine > 0.95) and explicitly flags contradictions between statute, regulation, and precedent rather than silently resolving them. Retrieval latency, request counts, and mode breakdowns are instrumented with Prometheus and visualized in Grafana.

> **⚠️ Disclaimer**: This system does NOT provide legal advice. All outputs are informational only and based on retrieved statutory text. Consult a qualified attorney for legal guidance.

---

## Related Project

This system is regression-tested by a standalone eval harness:  
👉 [legal-rag-eval](https://github.com/yourusername/legal-rag-eval)

Latest baseline scores:

| Metric             | Score | Threshold | Status   |
|--------------------|-------|-----------|----------|
| Hallucination Rate | TBD   | < 10%     | Run eval |
| Citation Accuracy  | TBD   | > 80%     | Run eval |
| Answer Relevancy   | TBD   | > 70%     | Run eval |
| Source Attribution | TBD   | > 75%     | Run eval |
| Conflict Detection | TBD   | > 80%     | Run eval |

TBD values are filled after the first eval run against a live Qdrant instance.

---

## Architecture

```mermaid
flowchart LR
    User([User]) --> FE[Next.js Frontend]
    FE --> API[FastAPI :8000]
    API --> LG[LangGraph Router]

    LG -- FEDERAL --> FR[federal_retriever]
    LG -- CFR_REGULATION --> CR[cfr_retriever]
    LG -- CASE_LAW --> CL[case_law_retriever]
    LG -- CROSS_SOURCE --> SM[source_merger]
    LG -- DOCUMENT --> DR[document_retriever]

    SM --> FR
    SM --> CR
    SM --> CL
    SM --> CD[conflict detection]

    FR --> QF[(federal_corpus\nQdrant)]
    CR --> QC[(cfr_corpus\nQdrant)]
    CL --> QL[(case_law_corpus\nQdrant)]
    DR --> QD[(user_docs\nQdrant)]

    QF --> LLM[gpt-4o]
    QC --> LLM
    QL --> LLM
    QD --> LLM
    CD --> LLM
    LLM --> Resp([Response + Citations])

    API --> PROM[/metrics → Prometheus :9090]
    Celery[Celery Workers] --> QF
    Celery --> QC
    Celery --> QL
    Celery --> QD
```

---

## Data Sources

| Source           | Coverage                                         | Qdrant Collection  | Status |
|------------------|--------------------------------------------------|--------------------|--------|
| U.S. Code        | Titles 8, 11, 15, 18, 26, 28, 29, 42            | federal_corpus     | Active |
| CFR              | Title 26 (Tax), Title 29 (Labor)                 | cfr_corpus         | Active |
| Case Law         | Federal precedential opinions 2000–present       | case_law_corpus    | Active |
| Uploaded Documents | PDF / DOCX / TXT                               | user_docs          | Active |

---

## Retrieval Modes

| Mode             | Triggers On                                    | Sources                          | Conflict Detection |
|------------------|------------------------------------------------|----------------------------------|--------------------|
| FEDERAL          | statute questions, U.S.C. references           | federal_corpus                   | No                 |
| CFR_REGULATION   | regulation questions, C.F.R. references        | cfr_corpus                       | No                 |
| CASE_LAW         | precedent / court held / ruling questions      | case_law_corpus                  | No                 |
| CROSS_SOURCE     | interpretation spanning statute + reg + case   | all three corpora + SourceMerger | Yes                |
| DOCUMENT         | uploaded file questions                        | user_docs                        | No                 |

**Mode isolation rule:** each retriever accesses exactly one collection. Violations are caught in `verify_answer` and cause the answer to be rejected. CROSS_SOURCE is the only mode that crosses collections, and it does so explicitly through `SourceMerger`.

---

## Local Setup

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+

### Environment Variables

Copy the example file and fill in the required secrets:

```bash
cp infra/.env.example infra/.env
```

Required variables:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for embeddings and LLM |
| `QDRANT_HOST` | Qdrant host (default: `qdrant` in Docker, `localhost` locally) |
| `QDRANT_API_KEY` | Only required for Qdrant Cloud |
| `COURTLISTENER_API_KEY` | Free research token from [courtlistener.com](https://www.courtlistener.com/sign-in/) — required for case law ingestion |
| `QDRANT_CASE_LAW_COLLECTION` | Qdrant collection name for case law (default: `case_law_corpus`) |
| `CASE_LAW_MAX_OPINIONS_PER_TITLE` | Max opinions to fetch per USC title (default: `500`) |

### Local Development

```bash
# 1. Clone and configure
cp infra/.env.example infra/.env

# 2. Start infrastructure
docker compose -f infra/docker-compose.yml up -d

# 3. Run backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 4. Run frontend
cd frontend
npm install
npm run dev

# 5. Ingest federal corpus
python -m app.ingestion.run_ingestion
```

### Ingest Case Law

```bash
# Requires COURTLISTENER_API_KEY in environment
python -m app.ingestion.case_law_ingestion
```

---

## Docker Deployment

```bash
docker compose -f infra/docker-compose.yml --profile full up --build
```

---

## Deployment (100% Free Forever Stack)

This project is optimized to run entirely on the **Free Tiers** of various cloud providers, ensuring $0/month cost.

### 1. Provision Free Services

You will need to create free accounts and get connection strings from these providers:

- **Frontend & Backend**: [Render](https://render.com) (Free Web Service)
- **Database**: [Supabase](https://supabase.com) (Free Postgres)
- **Vector Store**: [Qdrant Cloud](https://qdrant.tech/cloud/) (Free Cluster)
- **Redis (Cache/Queue)**: [Upstash](https://upstash.com) (Free Redis)

### 2. Configure Render Blueprint

1. Log in to [Render](https://dashboard.render.com/) and click **New > Blueprint**.
2. Connect your GitHub repository.
3. Render will detect the `render.yaml` file. Click **Apply**.
4. In the Render dashboard, go to the **backend** service and set these Environment Variables:
   - `DATABASE_URL`: Your Supabase URI (`postgresql://...`)
   - `REDIS_URL`: Your Upstash Redis URL (`redis://...`)
   - `QDRANT_HOST`: Your Qdrant Cloud Cluster URL (`https://...`)
   - `QDRANT_API_KEY`: Your Qdrant Cloud API Key
   - `OPENAI_API_KEY`: Your OpenAI API Key
   - `COURTLISTENER_API_KEY`: Your CourtListener research token

### 3. Data Ingestion (Free Tier)

Since Render's free tier has no persistent disk, the corpus data is ingested locally and pushed to Qdrant Cloud:

```bash
# In your local backend folder — point at Qdrant Cloud
export QDRANT_HOST="https://your-qdrant-cloud-url"
export QDRANT_API_KEY="your-api-key"
export COURTLISTENER_API_KEY="your-courtlistener-token"

# Ingest federal corpus (U.S. Code XML)
python -m app.ingestion.run_ingestion

# Ingest case law (CourtListener API — ~1 req/sec, allow several hours)
python -m app.ingestion.case_law_ingestion
```

For a step-by-step Oracle Cloud deployment see [ORACLE_DEPLOYMENT.md](docs/ORACLE_DEPLOYMENT.md).

---

## API Endpoints

| Endpoint        | Method | Description                                              |
|-----------------|--------|----------------------------------------------------------|
| `/chat`         | POST   | Submit a query (auto-detects mode or uses explicit mode) |
| `/upload`       | POST   | Upload PDF/DOCX/TXT for document Q&A                    |
| `/retrieval`    | POST   | Direct retrieval endpoint for testing                    |
| `/health`       | GET    | Overall health check                                     |
| `/health/live`  | GET    | Liveness probe                                           |
| `/health/ready` | GET    | Readiness probe                                          |
| `/metrics`      | GET    | Prometheus metrics endpoint                              |

---

## Tech Stack

| Layer              | Technology                                        |
|--------------------|---------------------------------------------------|
| Frontend           | Next.js, React, Tailwind CSS                      |
| Backend            | Python, FastAPI, Uvicorn, Pydantic                |
| Agent Framework    | LangGraph (13-node workflow)                      |
| Database           | PostgreSQL, SQLAlchemy, Alembic                   |
| Cache / Queue      | Redis, Celery                                     |
| Vector Store       | Qdrant (4 isolated collections)                   |
| LLM / Embeddings   | OpenAI gpt-4o, text-embedding-3-small (1536-d)    |
| Federal Corpus     | lxml, USLM XML parsing                            |
| Case Law           | CourtListener REST API v4                         |
| Document Parsing   | PyMuPDF, python-docx, pdfplumber                  |
| Observability      | Prometheus, Grafana, Loki, Promtail               |
| Infra              | Docker, Docker Compose, Nginx                     |

---

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/                  # FastAPI routes
│   │   ├── agents/               # LangGraph 13-node workflow
│   │   ├── retrieval/            # FederalRetriever, CfrRetriever,
│   │   │                         #   CaseLawRetriever, DocumentRetriever,
│   │   │                         #   SourceMerger
│   │   ├── ingestion/            # Federal XML, CFR XML, Case Law ingestion
│   │   ├── document_ingestion/   # PDF/DOCX/TXT processing
│   │   ├── database/             # SQLAlchemy models + Alembic
│   │   ├── services/             # Business logic / service layer
│   │   ├── observability/        # Prometheus metrics
│   │   ├── workers/              # Celery tasks
│   │   ├── core/                 # Config, settings, schemas, LLM client
│   │   └── tests/                # Test suite
│   ├── alembic/                  # Database migrations
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── infra/
│   ├── docker-compose.yml
│   ├── nginx.conf
│   ├── prometheus/
│   ├── grafana/
│   └── .env.example
├── DECISIONS.md                  # Architecture Decision Records (ADR-001–010)
├── docs/
└── sample_data/
```

---

## License

MIT
